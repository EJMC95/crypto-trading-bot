#!/usr/bin/env python3
"""study_prospect_admission.py — CAN the incubator's prospects join the fleet?

WHY (2026-07-29, operator: "can we test if they are able to join the fleet").
The prospect register carries genotypes that look admissible on their face —
the best read net +$39.81, lcb 22.29, 28 closes, BOTH HALVES POSITIVE. That is
the shape of something that should get its own book. The question this script
answers is whether that shape survives contact with the fleet the genotype
would actually join.

THE TEST, and why it is the decisive one. `strategy_incubator.evaluate()`
takes a `lenses` argument precisely because the replay harness is VETO-BLIND
by design: it will happily fill a lens the live/shadow taker refuses to trade.
A prospect's recorded score is therefore an upper bound, not an entry ticket.
So each genotype is scored TWICE on the same tape, through the incubator's own
`evaluate` (not a parallel implementation):

  ALL-LENS      every lens the harness can fill  — reproduces the register's
                recorded number, and is the sanity check that this script is
                measuring the same thing the register did.
  FLEET-FILLABLE  only the lenses `live_lenses(fresh_lens_fwd(...))` says the
                fleet will fill RIGHT NOW — i.e. the trades the book would
                actually get to make.

The gap between the two IS the answer. Then the survivor (if any) is put
through `assess_champion` — the incubator's real anti-overfit gate (closes
floor, both halves by margin, edge over the default genome, persistence) —
so admission is decided by the fleet's own bar, not by this script's opinion.

A genotype "can join the fleet" only if it clears the gate on FLEET-FILLABLE
lenses. Anything else is an edge measured on trades nobody will take — the
trap this repo has already recorded once ("ten of the tape's eleven closes
came from lenses the live bot refuses to trade").

VERDICT AS RUN (2026-07-29, tape 2200 snaps / 184h from db; fillable = {dip};
breakout/momentum/divergence all brain-vetoed):

  * NONE of the 30 register genotypes clears the gate. Not one.
  * 30 register rows reduce to **16 distinct experiments** once vetoed-lens
    genes are removed — nearly half the "roster" is copies differing only in
    a BRK_RANGE the fleet cannot exercise.
  * THE HEADLINE NUMBERS DO NOT REPRODUCE. The best prospect's recorded
    +$39.81 re-scores to **-$11.12 all-lens** on today's tape. The register
    stores `best_net`/`best_lcb` — a HIGH-WATER MARK from the day it was
    scored, deliberately ("never regress on a worse re-score"). That is right
    for a register and wrong for an admission decision: read `best_*` as a
    record, never as a current reading.
  * What survives the veto is ~flat and fails both halves anyway: the best
    fleet-fillable is +$7.65 with h2 **-8.86**, and every candidate lands
    9-11 fillable closes against a 40-close floor. The single fillable lens
    (dip) simply does not trade enough on this tape to have a fitness.
  * The DEFAULT genome is also negative (-$24.73 all-lens, -$10.27 fillable),
    so this is not a candidate-selection problem — the whole taker surface is
    negative on this window, corroborating the recorded finding that no taker
    lens is significantly positive.

Read-only: loads the tape and the register, scores in memory, writes nothing.
No lever, no book, no dashboard row is created by running this.

Usage:
  DATABASE_URL=... python3 scripts/study_prospect_admission.py
  python3 scripts/study_prospect_admission.py --selftest
"""
import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

import bot_pnl_store as store                    # noqa: E402
import lighter_ticket_replay as rp               # noqa: E402
import strategy_incubator as si                  # noqa: E402


def default_genotype():
    """The shipped taker bars — the baseline every candidate must BEAT."""
    return {g: getattr(si.tt, g) for _l, (g, _grid) in
            ((l, (gene, None)) for l, gene in si.LENS_GENE.items())
            if hasattr(si.tt, g)}


def collect(state, min_closes=1):
    """Distinct prospect genotypes from the register, best-first by best-ever
    lcb. Deduped on the incubator's own signature so float reprs cannot mint
    twins."""
    seen, out = set(), []
    rows = [e for e in (state.get("prospects") or [])
            if isinstance(e, dict) and (e.get("closes") or 0) >= min_closes]
    rows.sort(key=lambda e: (e.get("best_lcb") or 0.0), reverse=True)
    for e in rows:
        gt = e.get("genotype") or {}
        sig = si._sig(gt)
        if sig in seen:
            continue
        seen.add(sig)
        out.append(e)
    return out


def fillable_signature(gt, allowed):
    """The genotype REDUCED to genes the fleet can still exercise.

    Two prospects that differ only in a VETOED lens's gene are the same
    experiment once the veto is applied — reporting them as separate
    candidates would inflate the roster with copies. `evolvable_genes` is the
    incubator's own rule for which gene belongs to which lens."""
    keep, _dropped = si.evolvable_genes(
        {g: (lev, grid) for g, (lev, grid) in si.TAKER_GENES.items()}, allowed)
    return si._sig({g: v for g, v in gt.items() if g in keep})


def _fmt(r):
    return (f"net {r['net']:>8.2f}  h1 {r['h1']:>7.2f}  h2 {r['h2']:>7.2f}  "
            f"closes {r['closes']:>3d}  lcb {r['lcb']:>7.2f}  "
            f"both_halves {'YES' if r['both_halves_pos'] else 'no '}")


def _selftest():
    """Offline: the reduction logic, no tape, no DB."""
    a = {"BRK_RANGE": 0.95, "DIP_RANGE": 0.05, "TAKE_PROFIT": 0.06}
    b = {"BRK_RANGE": 0.90, "DIP_RANGE": 0.05, "TAKE_PROFIT": 0.06}
    # with breakout VETOED the two collapse to one experiment...
    assert fillable_signature(a, {"dip"}) == fillable_signature(b, {"dip"}), \
        "genotypes differing only in a vetoed lens's gene are ONE candidate"
    # ...and with breakout allowed they are genuinely different
    assert fillable_signature(a, {"dip", "breakout"}) != \
        fillable_signature(b, {"dip", "breakout"})
    # collect(): dedupes on signature, orders by best-ever lcb, honours floor
    st = {"prospects": [
        {"genotype": a, "closes": 10, "best_lcb": 1.0},
        {"genotype": dict(a), "closes": 10, "best_lcb": 9.0},   # dup sig
        {"genotype": b, "closes": 10, "best_lcb": 5.0},
        {"genotype": {"DIP_RANGE": 0.11}, "closes": 0, "best_lcb": 99.0},
    ]}
    got = collect(st, min_closes=1)
    assert len(got) == 2, got                       # dup dropped, 0-close dropped
    assert got[0]["best_lcb"] == 9.0, got           # best-ever lcb leads
    assert collect({}, 1) == [] and collect({"prospects": None}, 1) == []
    print("study_prospect_admission selftest OK (veto reduction, dedupe, "
          "ordering, empty-state)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--min-closes", type=int, default=1,
                    help="ignore register rows below this many closes")
    a = ap.parse_args()
    if a.selftest:
        return _selftest()

    tape, used = rp.load_tape(source="auto")
    if len(tape) < si.MIN_SNAPS:
        raise SystemExit(f"tape too short ({len(tape)}/{si.MIN_SNAPS}) — "
                         f"nothing can be judged on it")
    hours = (tape[-1][0] - tape[0][0]).total_seconds() / 3600.0
    now = si.now_ts()
    lens_fwd = si.fresh_lens_fwd(store.load_state("brain-lens-forward"), now)
    allowed = si.live_lenses(lens_fwd)
    vetoed = sorted(set(si.LENS_GENE) - allowed)

    print(f"tape {len(tape)} snaps / {hours:.0f}h (source={used})")
    print(f"lenses the fleet WILL fill : {sorted(allowed) or '(none)'}")
    print(f"lenses brain-VETOED        : {vetoed or '(none)'}")
    print(f"champion gate: >={si.MIN_CLOSES} closes, each half >= "
          f"${si.HALF_MARGIN:.2f}, beat default by >= ${si.EDGE_MARGIN:.2f}, "
          f"{si.PERSIST_CYCLES} consecutive cycles\n")

    reg = store.load_state(si.KEY) or {}
    cands = collect(reg, a.min_closes)
    if not cands:
        raise SystemExit("no prospects in the register above the closes floor")

    dflt = default_genotype()
    d_all = si.evaluate(dflt, tape, None)
    d_fit = si.evaluate(dflt, tape, allowed)
    print(f"DEFAULT genome (the bar to beat)")
    print(f"   all-lens        {_fmt(d_all)}")
    print(f"   fleet-fillable  {_fmt(d_fit)}\n")

    seen_reduced, rows = {}, []
    for e in cands:
        gt = e["genotype"]
        red = fillable_signature(gt, allowed)
        r_all = si.evaluate(gt, tape, None)
        r_fit = si.evaluate(gt, tape, allowed)
        rows.append((e, r_all, r_fit, red))
        seen_reduced.setdefault(red, []).append(e)

    print(f"{len(cands)} distinct register genotypes -> "
          f"{len(seen_reduced)} distinct experiments once the veto is applied"
          f" (differ only in vetoed-lens genes)\n")

    admitted = []
    for e, r_all, r_fit, _red in rows[:12]:
        print(f"* recorded: net {e.get('net'):.2f} lcb {e.get('best_lcb'):.2f} "
              f"closes {e.get('closes')}  role={e.get('role')}")
        print(f"   genotype        {e['genotype']}")
        print(f"   all-lens        {_fmt(r_all)}")
        print(f"   fleet-fillable  {_fmt(r_fit)}")
        ok, streak, stable, conf, why = si.assess_champion(
            {"genotype": e["genotype"], **r_fit}, d_fit["net"], hours,
            None, 0)
        print(f"   ADMISSION       {'PASS' if ok else 'REJECT'} "
              f"({conf}) — {why}\n")
        if ok:
            admitted.append(e)

    print("=" * 72)
    if admitted:
        print(f"{len(admitted)} genotype(s) CLEAR the gate on lenses the fleet "
              f"will fill. A book is still a BUILD, not an automatic step.")
    else:
        print("NONE clear the gate on lenses the fleet will fill. Compare the "
              "`recorded:` line against `all-lens` above before concluding "
              "WHY — the two failure modes are different and both are live:")
        print("  (1) STALE TAPE — the register stores each genotype's "
              "best-ever score, taken on the tape of the day it was scored. "
              "Re-scored on today's tape the same genotype can be NEGATIVE. "
              "A best-ever field is a high-water mark, not a current reading.")
        print("  (2) VETOED LENSES — what edge remains sits in lenses the "
              "brain has since vetoed, i.e. on trades nobody will take; the "
              "fleet-fillable row is the honest one.")
    print("A single cycle is not admission either: the gate wants "
          f"{si.PERSIST_CYCLES} consecutive cycles agreeing.")


if __name__ == "__main__":
    main()
