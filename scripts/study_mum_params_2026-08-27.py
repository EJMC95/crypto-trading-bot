#!/usr/bin/env python3
"""STUDY: 👩 mum v2 PARAMETER MAXIMISATION — the bar at 32, and the hold.
[2026-08-27, Eamon: "Widen mum to 32, maximise her optics metrics and
parameters."]

METHOD — PRE-DECLARED BEFORE ANY NUMBER WAS COMPUTED (I19). This file is
committed BEFORE the run, the (to)/(tq)/(tr) pre-registration pattern: the
bars and the verdict logic are fixed here first and the data may not move them.

It REUSES `study_mum_supply_2026-08-26` by import — the tape fetch, the
cluster-t estimator, the roi ladder and the bracket walk all have ONE owner
((hj): a second copy of a rule is a second rule). Only the CELLS, the hold
sweep and the verdict logic are new.

===========================================================================
Q1 — THE BAR. Does rsi<30 -> rsi<32 carry information, or is it the decayed
region (tr) already refused?

(tr) measured C4 = rsi [30,42) & NOT-uptrend and REFUSED it: trailing t_cl
-2.6..-3.0, decay deepening to -3.09 at 90d. Eamon's ask is 30 -> 32, which
is the LOWEST 2 points of that refused band. A band verdict is not a sliver
verdict — [30,32) may behave like its neighbour [25,30) (ADMITTED at +0.104%
/trade) rather than like the [34,42) tail that likely drove C4's decay. That
is an open empirical question and it is what this measures.

  CELLS (all `AND NOT uptrend`, mum's own entry conjunct, v>0 on the bar):
    D0  rsi [25,30)   -- CALIBRATION CONTROL. (tr) ADMITTED this cell at
                         +0.104%/trade, t=+2.38, t_cl=+1.99, both halves
                         positive, exit-free h12 excess +0.156% t_cl +2.25.
                         THE HARNESS MUST REPRODUCE IT. (gx): a harness that
                         cannot reproduce what DID happen may not say what
                         WOULD have. If D0 misses, every D-cell below is
                         WITHHELD, not reported with a caveat.
    D1  rsi [30,32)   -- THE ASK.
    D2  rsi [32,34)   -- boundary sweep: is the decay monotone in rsi? A
                         cell that is fine at [30,32) and bad at [32,34)
                         says "the bar belongs at 32"; one that is bad at
                         both says the region is dead from 30 up.
    D3  rsi [30,42)   -- CONTROL 2: reproduce (tr)'s REFUSED C4.

  A cell is graded exit-free FIRST ((qu): ~600 bracket sweeps failed because
  there was no entry edge for any bracket to harvest), against the matched-
  random null ((hm)), on the full window AND the trailing 120d ((qu)'s decay
  finding), then through mum's REAL bracket.

  VERDICT PER CELL, PRE-DECLARED:
    ADMIT      exit-free excess > 0 in BOTH windows with t_cl >= 1.5 at
               h=12 or h=24, AND real-bracket mean > 0 in BOTH chronological
               halves.
    HYPOTHESIS positive but under one or more bars — state exactly which.
    REFUSE     flat or negative — state the number.

===========================================================================
Q2 — THE HOLD. (tr) shipped a 24h max_hold and flagged it as a drag in its
own watch items: "max_hold exits -1.11%/trade; the surviving edge lives <=12h
where the roi ladder banks 70% of exits — if the control corroborates, a
max-hold tightening toward 12h is the NEXT measured candidate."

  Swept on mum's SHIPPED cell as she runs TODAY (rsi < 30 & NOT uptrend --
  i.e. (tr)'s B u C3), holding entries CONSTANT and varying ONLY the exit:
    MAX_HOLD in {8, 12, 16, 20, 24} bars (24 = shipped control)

  THE (hl) GUARD, AND IT IS THE WHOLE POINT OF THIS HALF. 25 of 30 "faster
  exit" candidates died in refutation because the gain was DENOMINATOR
  SHRINKAGE: a shorter hold books more trades of smaller size and the
  per-trade mean rises while the money does not. So this reports, for every
  cell:
      mean %/trade          -- the number that flatters a short hold
      RETURN PER BAR-DAY    -- mean_pct / (mean_hold_bars / 24)
      episodes/day, total % across the window at matched exposure
  and the verdict bar is written on the SECOND, not the first.

  VERDICT, PRE-DECLARED:
    ADMIT a shorter hold only if ALL of:
      (a) mean %/trade         >= shipped (24) -- it must not cost per trade
      (b) return per bar-day   >  shipped (24) -- it must not be pure churn
      (c) BOTH chronological halves positive
      (d) cluster-t >= shipped's cluster-t     -- not bought with variance
    Anything else: REFUSE, and print (a)-(d) so the refusal carries numbers.
    A refusal is a first-class outcome (CLAUDE.md standing rule).

  NOTE ON SCOPE: the roi LADDER is held fixed. Sweeping the ladder and the
  hold together is a two-variable change and the fleet's own rule is that an
  A/B varies exactly ONE variable; the ladder is the next candidate, not
  this one.

Usage:  .venv/bin/python3 scripts/study_mum_params_2026-08-27.py
Cache:  shares $MUM_SUPPLY_CACHE with the (tr) study — candles only.
"""
import importlib.util
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

_spec = importlib.util.spec_from_file_location(
    "mum_supply", os.path.join(HERE, "study_mum_supply_2026-08-26.py"))
S = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(S)                       # ONE owner for tape+stats

import lighter_family_bot as fb

# ---- pre-declared constants ----------------------------------------------
SEED = 20260827
HORIZONS = S.HORIZONS                              # (8, 12, 24)
DRAWS = S.DRAWS                                    # 1000
TRAIL_D = S.TRAIL_D                                # 120
T_BAR = S.T_BAR                                    # 1.5
WARMUP = S.WARMUP

# Q1 cells — (label, predicate over (rsi, uptrend))
CELLS = {
    "D0": ("rsi 25-30 & NOT-up  [CONTROL: (tr) ADMIT]",
           lambda r, up: 25 <= r < 30 and not up),
    "D1": ("rsi 30-32 & NOT-up  [THE ASK]",
           lambda r, up: 30 <= r < 32 and not up),
    "D2": ("rsi 32-34 & NOT-up  [boundary sweep]",
           lambda r, up: 32 <= r < 34 and not up),
    "D3": ("rsi 30-42 & NOT-up  [CONTROL: (tr) REFUSE]",
           lambda r, up: 30 <= r < 42 and not up),
}
CELL_ORDER = ["D0", "D1", "D2", "D3"]

# (tr)'s published D0 result — the calibration target.
CTRL_BRACKET_MEAN = 0.104        # %/trade
CTRL_TOL = 0.060                 # abs %/trade; wider than (tr)'s own halves gap
CTRL_H12_EXCESS = 0.156          # %

# Q2 — mum's shipped cell today, and the hold grid
SHIPPED_CELL = ("rsi<30 & NOT-up (shipped today)",
                lambda r, up: r < 30 and not up)
HOLDS = [8, 12, 16, 20, 24]
SHIPPED_HOLD = 24


def bracket_walk_h(bars, e, max_hold):
    """S.bracket_walk with an explicit hold. Same rules, one owner: the roi
    ladder and the stop come from S, only the horizon moves."""
    entry = bars[e][1]
    stop_px = entry * (1.0 + S.STOP)
    for k in range(e, min(e + max_hold, len(bars))):
        thr = S.roi_thr((k - e) * 60)
        if bars[k][3] <= stop_px:            # stop first — conservative
            return S.STOP * 100.0, "stop", k - e
        if bars[k][2] >= entry * (1.0 + thr):
            return thr * 100.0, "roi", k - e
    if e + max_hold >= len(bars):
        return None
    return (bars[e + max_hold][1] / entry - 1.0) * 100.0, "max_hold", max_hold


def halves(xs):
    if len(xs) < 4:
        return None, None
    m = len(xs) // 2
    return (sum(xs[:m]) / m, sum(xs[m:]) / (len(xs) - m))


def main():
    random.seed(SEED)
    mids = S.market_ids()
    syms = [s for s in (list(fb.COINS) + list(fb.NONCRYPTO_UNIVERSE))
            if s in mids]
    print(f"universe: {len(syms)} symbols (mum has no coins override)")

    tape, rsi, up = {}, {}, {}
    for s in syms:
        try:
            b = S.fetch_1h(s, mids[s])
        except Exception as e:                                  # noqa: BLE001
            print(f"  skip {s}: {type(e).__name__}")
            continue
        if len(b) < WARMUP + 50:
            continue
        closes = [x[4] for x in b]
        tape[s] = b
        rsi[s] = fb.rsi_series(closes, S.RSI_P)
        e50, e200 = fb.ema_series(closes, 50), fb.ema_series(closes, 200)
        up[s] = [None if (e50[i] is None or e200[i] is None) else e50[i] > e200[i]
                 for i in range(len(closes))]
    print(f"tape: {len(tape)} symbols with >= {WARMUP + 50} 1h bars")
    if not tape:
        print("NO TAPE — refusing to report (po: empty output is not a result)")
        return 2

    days = {s: (tape[s][-1][0] - tape[s][0][0]) / 86400.0 for s in tape}
    print(f"coverage: median {sorted(days.values())[len(days) // 2]:.0f}d, "
          f"min {min(days.values()):.0f}d, max {max(days.values()):.0f}d")

    def episodes_for(pred):
        """(sym, i) first-bar-of-run episodes, LAG-1 entry at open of i+1."""
        out, prev = [], {}
        for s, b in tape.items():
            for i in range(WARMUP, len(b) - max(HORIZONS) - 2):
                r, u, v = rsi[s][i], up[s][i], b[i][5]
                ok = (r is not None and u is not None and v > 0
                      and pred(r, u))
                if ok and not prev.get(s):
                    out.append((s, i))
                prev[s] = ok
        return out

    def exit_free(eps, h):
        """(mean_pct, excess_pct, t_cl, p_rand) at horizon h."""
        rets, ex, keys = [], [], []
        for s, i in eps:
            b = tape[s]
            e = i + 1
            if e + h >= len(b):
                continue
            rr = (b[e + h][1] / b[e][1] - 1.0) * 100.0
            allb = [(b[k + h][1] / b[k][1] - 1.0) * 100.0
                    for k in range(WARMUP, len(b) - h - 1, 12)]
            nullm = sum(allb) / len(allb) if allb else 0.0
            rets.append(rr)
            ex.append(rr - nullm)
            keys.append((s, b[e][0] // 86400))
        if len(rets) < 5:
            return None
        mean = sum(rets) / len(rets)
        t_cl = S.cluster_t(ex, keys)[0]      # cluster_t returns (t, G)
        # matched-random null
        bycoin = {}
        for s, i in eps:
            bycoin[s] = bycoin.get(s, 0) + 1
        hits = 0
        for _ in range(DRAWS):
            tot, n = 0.0, 0
            for s, cnt in bycoin.items():
                b = tape[s]
                lo, hi = WARMUP, len(b) - h - 2
                if hi <= lo:
                    continue
                for _ in range(cnt):
                    k = random.randint(lo, hi)
                    tot += (b[k + h][1] / b[k][1] - 1.0) * 100.0
                    n += 1
            if n and tot / n >= mean:
                hits += 1
        return (mean, sum(ex) / len(ex), t_cl, hits / DRAWS, len(rets))

    # ================= Q1 — THE BAR =================
    print("\n" + "=" * 78)
    print("Q1 — THE BAR: does rsi<30 -> rsi<32 carry information?")
    print("=" * 78)
    q1 = {}
    for cid in CELL_ORDER:
        label, pred = CELLS[cid]
        eps = episodes_for(pred)
        eps_tr = [(s, i) for s, i in eps if tape[s][i][0] >= S.TRAIL_TS]
        print(f"\n[{cid}] {label}")
        print(f"   episodes: {len(eps)} full · {len(eps_tr)} trailing-{TRAIL_D}d")
        if len(eps) < 20:
            print("   -> too few episodes to grade")
            q1[cid] = None
            continue
        row = {"n": len(eps), "n_tr": len(eps_tr)}
        for h in HORIZONS:
            f = exit_free(eps, h)
            t = exit_free(eps_tr, h) if len(eps_tr) >= 20 else None
            if not f:
                continue
            row[h] = (f, t)
            ts = (f"trail {t[1]:+.3f}% t_cl {t[2]:+.2f}"
                  if t else "trail n/a")
            print(f"   h={h:2d}: excess {f[1]:+.3f}%  t_cl {f[2]:+.2f}  "
                  f"P(rand>=cell) {f[3]:.3f}  |  {ts}")
        # real bracket
        br, keys, holds = [], [], []
        for s, i in eps:
            r = bracket_walk_h(tape[s], i + 1, SHIPPED_HOLD)
            if r:
                br.append(r[0])
                holds.append(r[2])
                keys.append((s, tape[s][i + 1][0] // 86400))
        if len(br) >= 10:
            h1, h2 = halves(br)
            row["br"] = (sum(br) / len(br), S.iid_t(br), S.cluster_t(br, keys)[0],
                         h1, h2, len(br))
            print(f"   BRACKET (24h): {sum(br)/len(br):+.3f}%/trade  "
                  f"t {S.iid_t(br):+.2f}  t_cl {S.cluster_t(br, keys)[0]:+.2f}  "
                  f"halves {h1:+.3f}/{h2:+.3f}  n={len(br)}")
        q1[cid] = row

    # ---- CALIBRATION GATE (gx): reproduce (tr)'s D0 or withhold -----------
    print("\n" + "-" * 78)
    ctrl = q1.get("D0") or {}
    cb = ctrl.get("br")
    ok = bool(cb) and abs(cb[0] - CTRL_BRACKET_MEAN) <= CTRL_TOL and cb[3] > 0 and cb[4] > 0
    if cb:
        print(f"CALIBRATION: D0 bracket {cb[0]:+.3f}%/trade vs (tr)'s "
              f"{CTRL_BRACKET_MEAN:+.3f}% (tol +/-{CTRL_TOL:.3f}), "
              f"halves {cb[3]:+.3f}/{cb[4]:+.3f}")
    else:
        print("CALIBRATION: D0 UNGRADED")
    print("  => " + ("PASS — the D-cells may be reported" if ok
                     else "FAIL — every D-cell verdict is WITHHELD (gx)"))

    print("\nQ1 VERDICTS:")
    for cid in ("D1", "D2", "D3"):
        row = q1.get(cid)
        if not ok:
            print(f"  {cid}: WITHHELD — harness failed its control")
            continue
        if not row or "br" not in row:
            print(f"  {cid}: UNGRADED — too few episodes")
            continue
        best = max((row[h][0][2] for h in HORIZONS if h in row), default=0)
        trail_pos = all((row[h][1] and row[h][1][1] > 0)
                        for h in (12, 24) if h in row and row[h][1])
        full_pos = all(row[h][0][1] > 0 for h in (12, 24) if h in row)
        m, _t, _tc, h1, h2, n = row["br"]
        admit = (full_pos and trail_pos and best >= T_BAR and h1 > 0 and h2 > 0)
        v = ("ADMIT" if admit else
             "HYPOTHESIS" if m > 0 else "REFUSE")
        print(f"  {cid}: {v} — bracket {m:+.3f}%/trade halves {h1:+.3f}/{h2:+.3f}"
              f" n={n}, best exit-free t_cl {best:+.2f},"
              f" full{'+' if full_pos else '-'} trail{'+' if trail_pos else '-'}")

    # ================= Q2 — THE HOLD =================
    print("\n" + "=" * 78)
    print("Q2 — THE HOLD: sweep max_hold on the SHIPPED cell, entries CONSTANT")
    print("=" * 78)
    eps = episodes_for(SHIPPED_CELL[1])
    span_d = max(days.values()) if days else 1.0
    print(f"shipped cell episodes: {len(eps)} over ~{span_d:.0f}d")
    print(f"\n{'hold':>5} {'n':>5} {'mean%/tr':>9} {'t':>6} {'t_cl':>6} "
          f"{'halves':>17} {'meanhold_h':>11} {'%/bar-day':>10} {'exits(roi/stop/hold)':>22}")
    q2 = {}
    for H in HOLDS:
        rr, keys, hold_bars, mix = [], [], [], {"roi": 0, "stop": 0, "max_hold": 0}
        for s, i in eps:
            r = bracket_walk_h(tape[s], i + 1, H)
            if not r:
                continue
            rr.append(r[0])
            hold_bars.append(r[2] if r[1] != "max_hold" else H)
            mix[r[1]] += 1
            keys.append((s, tape[s][i + 1][0] // 86400))
        if len(rr) < 10:
            continue
        mean = sum(rr) / len(rr)
        mh = sum(hold_bars) / len(hold_bars)
        perbd = mean / (mh / 24.0) if mh else 0.0
        h1, h2 = halves(rr)
        tc = S.cluster_t(rr, keys)[0]
        q2[H] = (mean, S.iid_t(rr), tc, h1, h2, mh, perbd, len(rr), mix)
        print(f"{H:5d} {len(rr):5d} {mean:+9.3f} {S.iid_t(rr):+6.2f} {tc:+6.2f} "
              f"{h1:+7.3f}/{h2:+7.3f} {mh:11.1f} {perbd:+10.3f} "
              f"{mix['roi']:6d}/{mix['stop']:5d}/{mix['max_hold']:5d}")

    print("\nQ2 VERDICT (bars pre-declared: (a) mean>=shipped (b) %/bar-day>shipped "
          "(c) both halves + (d) t_cl>=shipped):")
    base = q2.get(SHIPPED_HOLD)
    if not base:
        print("  UNGRADED — the shipped hold did not produce enough closes")
    else:
        bm, _bt, btc, _bh1, _bh2, _bmh, bpd, _bn, _bx = base
        for H in HOLDS:
            if H == SHIPPED_HOLD or H not in q2:
                continue
            m, _t, tc, h1, h2, _mh, pd, n, _x = q2[H]
            a, b, c, d = m >= bm, pd > bpd, (h1 > 0 and h2 > 0), tc >= btc
            v = "ADMIT" if (a and b and c and d) else "REFUSE"
            print(f"  hold={H:2d}h: {v} — (a) {m:+.3f} vs {bm:+.3f} {'OK' if a else 'NO'}"
                  f" · (b) {pd:+.3f} vs {bpd:+.3f} {'OK' if b else 'NO'}"
                  f" · (c) {h1:+.3f}/{h2:+.3f} {'OK' if c else 'NO'}"
                  f" · (d) t_cl {tc:+.2f} vs {btc:+.2f} {'OK' if d else 'NO'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
