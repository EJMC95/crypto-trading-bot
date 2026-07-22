#!/usr/bin/env python3
"""
scripts/backtest_xsect_funding_merged.py — does the funding-rank cross-section
get BETTER with breadth? crypto-only vs non-crypto-only vs MERGED, one window.

WHY THIS EXISTS (2026-07-22)
  backtest_xsect_funding_noncrypto.py failed (3/12, no plateau, h2 −3.3%) and
  its diagnosis was specific: **starved of breadth, not of signal.** The mirror
  was strongly negative in all 12 cells (−7.1..−36.6), the carry leg was bigger
  than crypto's (+4.2..+8.4pp vs +4.5pp), friction was measured and cheap
  (median 2.90bps/side) — but with 23 books and k=5 you hold 10 of 23, so two
  single names reversing (SNDK +5.5→−9.2, INTC +4.9→−8.3) flipped h2. k=5 beat
  k=3 in every pairing, which is the same story from the other side.

  If that diagnosis is right, MERGING the two cross-sections (~48 books) should
  help, because the failure was averaging, not the factor. If merging does NOT
  help, the diagnosis was wrong and the non-crypto books simply carry no
  transferable edge — which is equally worth knowing, and cheaper to learn here
  than in a shadow book.

THE HONEST RISK, NAMED UP FRONT
  Changing the universe after seeing a failure is one step from universe-fitting.
  Two protections: (1) the decision rule below is written BEFORE the run and is
  not adjusted afterwards; (2) the crypto-only arm is RE-RUN in this harness on
  THIS window rather than compared to the published +13.6% — otherwise the
  comparison silently varies the window as well as the universe
  (see [[ab-tests-must-vary-exactly-one-variable]]).

PRE-REGISTERED DECISION RULE  (written 2026-07-22 BEFORE the first run)
  All three arms run on the SAME common-hours window and the SAME 12-cell grid,
  with simulate()/gate()/align() imported verbatim from the validated control.

  MERGED SHIPS as 🏹 Tamerlane only if ALL of:
    D1. full > 0 AND h1 > 0 AND h2 > 0                    (both halves, doctrine)
    D2. mirror(price) < 0                                 (signal, not drift)
    D3. PLATEAU — >=4/12 cells pass AND the passing cells form a contiguous
        region (a shared lookback row or a shared k column), not scatter
    D4. maxDD < 15% on the chosen cell                    (the go-live gate)
    D5. still green in BOTH halves at 3x friction (15bps/side)
    D6. no monotone quarterly decay, and no quarter worse than −5%
    D7. **MERGED BEATS CRYPTO-ONLY on the same window** — on both full return
        and h2. If merged only matches crypto-only, the non-crypto books add
        nothing and the correct action is NOT a new bot.

  If D1-D6 pass but D7 fails -> the answer is "widen ⚖️ Counterweight's
  universe", a config change to a live-validated book, NOT a new bot.
  If D3 fails -> dead, same as the non-crypto run. Do not re-grid.

╔══════════════════════════════════════════════════════════════════════════════╗
║ VERDICT (2026-07-22, 150d, 3589 shared hours, three arms on ONE window)      ║
║ **THE BREADTH DIAGNOSIS IS REFUTED. 🏹 Tamerlane is DEAD — do not build it,  ║
║ and do NOT widen ⚖️ Counterweight either.** Adding the non-crypto books to   ║
║ the crypto cross-section makes it WORSE, not better.                        ║
╚══════════════════════════════════════════════════════════════════════════════╝
    arm (same 3589h window)      cells passing      48/5/24: full / h1 / h2
    crypto-only (live universe)     **11/12**        +8.5 / +7.0 / +6.9
    MERGED crypto + non-crypto        5/12          +19.2 / +19.8 / +5.7
    non-crypto only                   3/12          +19.7 / +20.8 / +2.4

  THE PRE-REGISTERED RULE, EVALUATED (rule written before the run, unadjusted):
    D3 plateau      5/12, scattered                                    weak
    D5 3x friction  15bps -> h2 −0.0%                                  **FAIL**
    D6 quarterly    q1 +10.2  q2 +9.2  q3 +1.0  q4 −4.0 = MONOTONE     **FAIL**
    D7 beats crypto-only on full AND h2   +19.2>+8.5 but +5.7<+6.9     **FAIL**
  Three of seven gates fail. Merged does not ship.

  WHAT THIS REFUTES — state it plainly, it was MY hypothesis:
  backtest_xsect_funding_noncrypto.py concluded the non-crypto book was
  "starved of breadth, not of signal", and predicted that merging (~48 books)
  would rescue it. **It did not.** Merging did the opposite: the crypto
  cross-section alone passes 11/12 cells on this window; diluting it with 23
  non-crypto books drops it to 5/12 and turns h2 from +6.9% to +5.7% while
  making the quarterly profile monotonically decaying. The pre-registration
  named this outcome in advance — "if merging does NOT help, the diagnosis was
  wrong and the non-crypto books simply carry no transferable edge." That is
  the outcome. The non-crypto funding rank is real (mirror negative everywhere,
  carry leg genuinely large at +8.1pp merged) but it does not SURVIVE, and it
  degrades a book that does.

  WHY the big non-crypto full-window numbers are a trap: merged/non-crypto post
  the biggest full% figures in the whole table (+31.6, +29.9) and they are the
  WORST cells — h1-loaded, h2-negative, mirror-huge. On a cross-section, a large
  full% with a large negative mirror and a weak h2 is an overfit fingerprint,
  not an edge. Rank cells by h2 and quarterly stability, never by full%.

  ACTIONS:
  * Do NOT build 🏹 Tamerlane. Do NOT re-grid (the grid is exhausted, 3 arms x 12).
  * Do NOT widen Counterweight's universe with non-crypto books — measured
    harmful (11/12 -> 5/12). Leave the live book alone.
  * The 150d re-run of the LIVE config (72/5/24, crypto-only) is healthy on this
    window: full +10.6 / h1 +5.1 / h2 +7.6 / maxDD 10.3 / mirror −19.6. That is a
    re-measurement, NOT a mandate to retune (k=3 cells look richer here but this
    is one window and the published plateau is the 72h row — do not chase them).
  * The non-crypto sleeve's remaining open question is NOT this factor. See
    backtest_xsect_funding_noncrypto.py's revisit condition (universe breadth at
    140d+ tape, ~Oct 2026) — but note this file has already weakened the case:
    breadth was tested here by proxy and did not help.

Read-only: public Lighter endpoints + the two sibling caches. No bot, no DB.
Usage:
    .venv/bin/python3 scripts/backtest_xsect_funding_merged.py
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from backtest_xsect_funding_lighter import (  # noqa: E402
    align, gate, simulate, HD, ORDER_USD, SLIP,
)
import backtest_xsect_funding_lighter as CRYPTO   # noqa: E402
import backtest_xsect_funding_noncrypto as NONX   # noqa: E402

GRID = [(fl, k, reb) for fl in (24, 48, 72) for k in (3, 5) for reb in (24, 48)]


def rank_factory(coins, fund):
    def mk_rank(seg, fl):
        def rank(i):
            sc = {}
            for c in coins:
                rs = [fund[c].get(seg[j]) for j in range(i - fl, i)]
                rs = [x for x in rs if x is not None]
                if len(rs) >= fl // 2:
                    sc[c] = -sum(rs) / len(rs)
            return sc
        return rank
    return mk_rank


def restrict(mk, hours):
    """Clip every book to a fixed hour set so all arms share ONE window."""
    out = {}
    for s, m in mk.items():
        f = {t: v for t, v in m["fund"].items() if t in hours}
        c = {t: v for t, v in m["cand"].items() if t in hours}
        if len(f) == len(hours) and len(c) == len(hours):
            out[s] = {"fund": f, "cand": c}
    return out


def run_arm(name, mk, hours):
    mkr = restrict(mk, hours)
    if len(mkr) < 12:
        print(f"\n{name}: only {len(mkr)} books span the shared window — skipped")
        return None
    coins, ts, px, fund = align(mkr)
    base = rank_factory(coins, fund)
    print(f"\n{'='*92}\nARM: {name}  — {len(coins)} books, {len(ts)}h "
          f"({(ts[-1]-ts[0])/86400:.0f}d)\n{'='*92}")
    hdr = (f"{'lb':>4} {'k':>2} {'reb':>4} | {'full%':>7} {'h1%':>7} {'h2%':>7} "
           f"{'dd%':>5} {'trips':>5} | {'mirror%':>8} {'fund_pp':>7} | verdict")
    print(hdr); print("-" * len(hdr))
    res, passes = {}, []
    for (fl, k, reb) in GRID:
        r = gate(coins, ts, px, fund, lambda seg, f=fl: base(seg, f),
                 fl + HD, k, reb)
        ok = (r["full"]["ret"] > 0 and r["h1"]["ret"] > 0 and r["h2"]["ret"] > 0
              and r["mirror"]["price"] < 0)
        res[(fl, k, reb)] = r
        if ok:
            passes.append((fl, k, reb))
        print(f"{fl:>4} {k:>2} {reb:>4} | {r['full']['ret']:>7.1f} "
              f"{r['h1']['ret']:>7.1f} {r['h2']['ret']:>7.1f} "
              f"{r['full']['dd']:>5.1f} {r['full']['trips']:>5} | "
              f"{r['mirror']['ret']:>8.1f} {r['full']['fund']:>7.1f} | "
              f"{'PASS' if ok else 'FAIL'}")
    print(f"  -> {len(passes)}/12 pass: {passes}")
    return {"coins": coins, "ts": ts, "px": px, "fund": fund, "base": base,
            "res": res, "passes": passes}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=150)
    ap.add_argument("--min-days", type=int, default=140)
    ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args()

    nx, _ = NONX.load(a.days, a.refresh, a.min_days * 24)
    cr = CRYPTO.load(a.days, a.refresh)
    print(f"\nloaded: {len(cr)} crypto books, {len(nx)} non-crypto books")

    merged = dict(cr)
    merged.update(nx)
    # ONE window for all three arms = the merged intersection.
    hours = set.intersection(*[set(m["cand"]) & set(m["fund"])
                               for m in merged.values()])
    print(f"shared window: {len(hours)}h across {len(merged)} books")
    if len(hours) < 24 * 60:
        # a single short book would truncate everything — drop the offenders
        by_len = sorted(merged.items(), key=lambda x: -len(x[1]["cand"]))
        keep = dict(by_len[:len(by_len) - 3])
        hours = set.intersection(*[set(m["cand"]) & set(m["fund"])
                                   for m in keep.values()])
        merged = keep
        print(f"  window too short — dropped 3 shortest books -> {len(hours)}h")

    arms = {}
    for name, mk in (("crypto-only (the live ⚖️ Counterweight universe)", cr),
                     ("non-crypto only", nx),
                     ("MERGED crypto + non-crypto", merged)):
        arms[name] = run_arm(name, mk, hours)

    # ---- D7 + quarterly on the merged arm's best contiguous cell -----------
    m = arms.get("MERGED crypto + non-crypto")
    c = arms.get("crypto-only (the live ⚖️ Counterweight universe)")
    if not (m and c):
        return
    print("\n" + "=" * 92)
    print("PRE-REGISTERED DECISION RULE — evaluated")
    print("=" * 92)
    print(f"D3 plateau : merged {len(m['passes'])}/12 pass -> {m['passes']}")

    cell = (72, 5, 24)
    if m["passes"]:
        cell = max(m["passes"], key=lambda p: m["res"][p]["h2"]["ret"])
    rm, rc = m["res"][cell], c["res"].get(cell)
    print(f"\nchosen cell {cell} (best h2 among merged passers)")
    print(f"  MERGED      full {rm['full']['ret']:+7.1f}%  h1 {rm['h1']['ret']:+7.1f}%"
          f"  h2 {rm['h2']['ret']:+7.1f}%  dd {rm['full']['dd']:5.1f}%"
          f"  mirror {rm['mirror']['price']:+7.1f}%  fund {rm['full']['fund']:+.1f}pp")
    if rc:
        print(f"  crypto-only full {rc['full']['ret']:+7.1f}%  h1 {rc['h1']['ret']:+7.1f}%"
              f"  h2 {rc['h2']['ret']:+7.1f}%  dd {rc['full']['dd']:5.1f}%"
              f"  mirror {rc['mirror']['price']:+7.1f}%  fund {rc['full']['fund']:+.1f}pp")
        d7 = (rm["full"]["ret"] > rc["full"]["ret"]
              and rm["h2"]["ret"] > rc["h2"]["ret"])
        print(f"\nD7 merged BEATS crypto-only on full AND h2: "
              f"{'PASS' if d7 else '**FAIL** -> widen Counterweight, do NOT build a new bot'}")

    print(f"\nD5 slip stress on {cell}:")
    fl, k, reb = cell
    for bps in (5, 10, 15):
        r = gate(m["coins"], m["ts"], m["px"], m["fund"],
                 lambda seg, f=fl: m["base"](seg, f), fl + HD, k, reb,
                 slip=bps / 1e4)
        both = r["h1"]["ret"] > 0 and r["h2"]["ret"] > 0 and r["full"]["ret"] > 0
        print(f"  {bps:>2}bps  full {r['full']['ret']:+7.1f}  h1 {r['h1']['ret']:+7.1f}"
              f"  h2 {r['h2']['ret']:+7.1f}   {'green' if both else '**NEGATIVE**'}")

    print(f"\nD6 quarterly on {cell}:")
    ts = m["ts"]; q = len(ts) // 4
    qs = []
    for i in range(4):
        seg = ts[i * q:(i + 1) * q]
        cc, pp, fp, dd, tr, w, g = simulate(m["coins"], seg, m["px"], m["fund"],
                                            m["base"](seg, fl), fl + HD, k, reb)
        qs.append(100 * cc / g)
    print("  " + "  ".join(f"q{i+1} {v:+.1f}%" for i, v in enumerate(qs)))
    mono = all(qs[i] >= qs[i + 1] for i in range(3))
    print(f"  monotone decay: {'YES -> D6 FAIL' if mono else 'no'}; "
          f"worst quarter {min(qs):+.1f}% "
          f"({'FAIL' if min(qs) < -5 else 'ok'} vs the −5% bar)")


if __name__ == "__main__":
    main()
