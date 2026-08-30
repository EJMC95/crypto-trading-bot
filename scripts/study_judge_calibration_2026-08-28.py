#!/usr/bin/env python3
"""What does the judge's promotion rule ACTUALLY do? — the calibrated instrument.

[2026-08-28 (vd)] Eamon: *"fix the promotion rule immediately"*.

`(vm)` published the mismatch and stopped there: the judge promotes on a
**0.5pp** margin while its binding rung can only resolve **1.986pp** (🔮
georgia; 1.658pp 🙏 avo). A 4x gap. But "under-powered" is only half a
diagnosis — a bar can be under-powered and still SAFE if it is conservative,
or under-powered and RECKLESS if it is not. Nobody had asked which.

THE RULE, read from `paired_eval` rather than described:
    per half   : (shadow_half_mean - live_half_mean) >= margin_pp
    full window: shadow_mean > 0 AND (shadow_mean - live_mean) >= margin_pp
    floors     : half_floors() = (15 shadow, 5 live); full 30/10

It is a pure MAGNITUDE test. There is no variance term anywhere in it, so it
cannot know whether an observed 0.6pp gap is signal or the sampling noise of a
5-trade half. That is the thing this measures.

WHAT THIS DOES: draws paired arms from the books' OWN measured dispersion,
applies the REAL decision arithmetic, and reports two numbers per rule —
  * FALSE PROMOTION: P(promote | true effect = 0). Promoting noise onto real
    money is the expensive error; the fade-watch is a backstop, not an excuse.
  * POWER: P(promote | true effect = the margin it claims to detect).
A rule wants low false-promotion AND usable power. The current rule is scored
first, and every candidate against it.

PRE-REGISTERED, before any result existed:
  P1 A candidate must have false-promotion <= the current rule's. A "fix" that
     promotes noise MORE often is a regression however good its power looks.
  P2 Among those, prefer the one with the most power at a 1.0pp true effect —
     a realistic improvement for these books, not the 0.5pp the bar names.
  P3 If NO candidate beats the current rule on both, say so and ship nothing.
     A refusal with evidence is a valid outcome (CLAUDE.md standing rule).
  P4 The arithmetic is IMPORTED from experiment_judge, never re-typed — a
     second copy of the promotion rule is a second rule ((hj)). If the import
     fails this study REFUSES rather than modelling its own guess.
"""
import argparse
import math
import os
import random
import statistics as st
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import experiment_judge as ej                                # noqa: E402

# The books' OWN measured dispersion, from the judge's published power block.
BOOKS = {
    "georgia": {"sd_live": 1.529, "sd_shadow": 3.005,
                "per_day_live": 3.64, "per_day_shadow": 8.07},
    "avo": {"sd_live": 1.863, "sd_shadow": 2.508,
            "per_day_live": 0.43, "per_day_shadow": 0.79},
}
WINDOW_D = 14.0


def _halves(xs):
    h = len(xs) // 2
    return xs[:h], xs[h:]


def rule_current(sh, lv, margin_pp):
    """The SHIPPED bar, re-expressed on plain samples so the simulation can
    drive it. Verified against `experiment_judge.paired_eval` on real rows by
    `_calibrate()` below — if they disagree this study refuses to speak."""
    hs, hl = ej.half_floors()
    if len(sh) < ej.MIN_CLOSES or len(lv) < ej.LIVE_MIN_CLOSES:
        return False
    for a, b in zip(_halves(sh), _halves(lv)):
        if len(a) < hs or len(b) < hl:
            return False
        if (st.mean(a) - st.mean(b)) < margin_pp:
            return False
    if st.mean(sh) <= 0:
        return False
    return (st.mean(sh) - st.mean(lv)) >= margin_pp


def _welch_t(a, b):
    if len(a) < 2 or len(b) < 2:
        return 0.0
    va, vb = st.variance(a), st.variance(b)
    se = math.sqrt(va / len(a) + vb / len(b))
    return (st.mean(a) - st.mean(b)) / se if se > 0 else 0.0


def rule_t(t_bar, halves_direction=True, margin_pp=0.0):
    """SIGNIFICANCE on the full window; halves used for DIRECTION only.

    The current rule asks each half to clear the full margin, which on a
    5-trade half is a coin flip dressed as a bar. This asks the pooled sample
    whether the gap is distinguishable from zero, and asks the halves only not
    to contradict each other — the both-halves DOCTRINE (no lucky week) without
    the magnitude demand the sample cannot support.
    """
    def _f(sh, lv, margin_pp_ignored=None):
        hs, hl = ej.half_floors()
        if len(sh) < ej.MIN_CLOSES or len(lv) < ej.LIVE_MIN_CLOSES:
            return False
        if st.mean(sh) <= 0:
            return False
        if (st.mean(sh) - st.mean(lv)) < margin_pp:
            return False
        if halves_direction:
            for a, b in zip(_halves(sh), _halves(lv)):
                if len(a) < hs or len(b) < hl:
                    return False
                if (st.mean(a) - st.mean(b)) <= 0:
                    return False
        return _welch_t(sh, lv) >= t_bar
    return _f


def simulate(book, rule, delta_pp, trials, seed):
    rng = random.Random(seed)
    b = BOOKS[book]
    n_sh = max(int(b["per_day_shadow"] * WINDOW_D), ej.MIN_CLOSES)
    n_lv = max(int(b["per_day_live"] * WINDOW_D), ej.LIVE_MIN_CLOSES)
    hits = 0
    for _ in range(trials):
        sh = [rng.gauss(delta_pp, b["sd_shadow"]) for _ in range(n_sh)]
        lv = [rng.gauss(0.0, b["sd_live"]) for _ in range(n_lv)]
        if rule(sh, lv, ej.MARGIN_PP):
            hits += 1
    return hits / trials, n_sh, n_lv


def _calibrate():
    """P4 — the shipped arithmetic must agree with my re-expression of it on
    the SAME rows, or nothing below is about the real judge.

    Fail-CLOSED: any disagreement, or a missing import, refuses the study.
    """
    rng = random.Random(20260828)
    checked = 0
    for _ in range(200):
        n_sh = rng.randint(ej.MIN_CLOSES, 60)
        n_lv = rng.randint(ej.LIVE_MIN_CLOSES, 40)
        d = rng.uniform(-1.5, 2.5)
        sh = [rng.gauss(d, 2.0) for _ in range(n_sh)]
        lv = [rng.gauss(0.0, 1.5) for _ in range(n_lv)]
        # THE FIXTURE BUG THE GATE CAUGHT, recorded because it is the whole
        # reason this check exists: `paired_eval` splits the halves by WINDOW
        # TIME, not by sample index. The first cut used a 10,000,000s window,
        # so every row landed in half 1, half 2 was EMPTY, the floors failed,
        # and `paired_eval` returned False while my index-split re-expression
        # said True. My arithmetic was right and my FIXTURE was wrong — and a
        # study that had not calibrated would have reported that disagreement
        # as a finding about the judge.
        #
        # Both arms are now spread EVENLY across one window, so the time
        # midpoint splits each arm exactly in half and index-split == time-split
        # by construction.
        t0, span = 1_700_000_000, 1_000_000
        rows = ([{"bot": "S", "profit_ratio": x / 100.0, "profit_abs": x,
                  "open_rate": 1.0,
                  "close_ts": t0 + int((i + 0.5) * span / n_sh)}
                 for i, x in enumerate(sh)]
                + [{"bot": "L", "profit_ratio": x / 100.0, "profit_abs": x,
                    "open_rate": 1.0,
                    "close_ts": t0 + int((j + 0.5) * span / n_lv)}
                   for j, x in enumerate(lv)])
        got = ej.paired_eval(rows, t0, t0 + span,
                             shadow_bot="S", live_bot="L")["promote"]
        mine = rule_current(sh, lv, ej.MARGIN_PP)
        if got != mine:
            return False, (f"disagreement at n_sh={n_sh} n_lv={n_lv} d={d:.2f}: "
                           f"paired_eval={got} re-expression={mine}")
        checked += 1
    return True, f"{checked} random samples, zero disagreement"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=4000)
    ap.add_argument("--seed", type=int, default=20260828)
    a = ap.parse_args()

    ok, detail = _calibrate()
    print(f"=== P4 CALIBRATION (fail-closed) ===\n  {detail}")
    if not ok:
        print("  VERDICT: REFUSED — my re-expression is not the shipped rule, "
              "so nothing below describes the judge.")
        return 2
    print("  VERDICT: the re-expression IS `paired_eval`. Proceeding.\n")

    cands = [
        (f"CURRENT (margin {ej.MARGIN_PP}pp both halves)",
         lambda sh, lv, m: rule_current(sh, lv, ej.MARGIN_PP)),
        ("t>=1.65 pooled + halves same sign",
         lambda sh, lv, m: rule_t(1.65)(sh, lv)),
        ("t>=2.0 pooled + halves same sign",
         lambda sh, lv, m: rule_t(2.0)(sh, lv)),
        ("t>=2.0 pooled + halves same sign + gap>=0.5pp",
         lambda sh, lv, m: rule_t(2.0, margin_pp=0.5)(sh, lv)),
        ("t>=2.5 pooled + halves same sign",
         lambda sh, lv, m: rule_t(2.5)(sh, lv)),
    ]
    deltas = [0.0, 0.5, 1.0, 2.0]
    for book in BOOKS:
        print(f"=== {book.upper()}  (sd live {BOOKS[book]['sd_live']}, "
              f"shadow {BOOKS[book]['sd_shadow']}; {WINDOW_D:.0f}d window) ===")
        hdr = "  " + f"{'rule':44}" + "".join(f"{('d=' + str(d) + 'pp'):>11}"
                                              for d in deltas)
        print(hdr)
        for label, fn in cands:
            cells = []
            for d in deltas:
                p, n_sh, n_lv = simulate(book, fn, d, a.trials, a.seed)
                cells.append(f"{100 * p:>10.1f}%")
            print(f"  {label:44}" + "".join(cells))
        print(f"  (n_shadow={n_sh}, n_live={n_lv} per trial; "
              f"d=0 is FALSE PROMOTION, the rest is POWER)\n")
    print("READ-ONLY. A candidate for review, not permission to ship it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
