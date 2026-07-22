#!/usr/bin/env python3
"""
scripts/ab_regime_oracle_venue_swap.py — did the HL->Lighter swap in
regime_oracle.py change the fleet's regime call? MEASURED, both live APIs.

WHY THIS EXISTS, given the equivalence study already ran.
study_lighter_vs_hl_equivalence.py proved a claim about DATA: "Lighter's 1d
candles, fed to regime_oracle's classify(), give the same verdict 99.4% of the
time". It did NOT prove a claim about CODE: that the fetch_daily() I actually
shipped — its backward paging, its 500-bar cap, its closed-bar rule, its
window trim — reproduces that. A swap is only proven by the code that ships.
So this drives regime_oracle's REAL fetch_daily()/market_ids() as the variant
arm, and the VERBATIM OLD HL fetch (lifted from git HEAD, still pre-swap) as
the control arm.

╔══════════════════════════════════════════════════════════════════════════════╗
║ VERDICT (2026-07-17, run against both live APIs; every number is this         ║
║ script's real output).                                                        ║
║                                                                              ║
║ 1. **NO COIN'S VERDICT CHANGES TODAY. 16/16 majors identical.** The shipped   ║
║    swap is a no-op on the live decision — and it is seed-INVARIANT: the two   ║
║    arms agree on all 16 coins under every hysteresis seed (None/0/1), so no   ║
║    coin is sitting on the ADX knife-edge where the sources could split today. ║
║                                                                              ║
║ 2. **60-DAY ROLLING REPLAY: 895/900 coin-days agree (99.4%).** 12 of the 15   ║
║    replayable majors agree 100%. The 5 disagreements: NEAR 07-15 + 07-16      ║
║    (2 CHARACTER flips), TAO 05-24 + 06-15 and DOGE 05-22 (3 DIRECTION).       ║
║    Independently reproduces the study (99.4% over 200d) from a DIFFERENT      ║
║    fetch path — and lands on NEAR 2026-07-15/07-16 with the same ADX to the   ║
║    decimal (HL LONG-window 13.0/13.4 vs Lighter chop-gated 12.0/12.3), which  ║
║    the study's header independently named as live-disagreeing.                ║
║                                                                              ║
║ 2b. THE REPLAY IS THE CONSERVATIVE INSTRUMENT — it OVERSTATES the live risk.  ║
║    It carries TWO INDEPENDENT hysteresis chains, so one band straddle latches ║
║    the arms apart for days. PRODUCTION HAS ONE CHAIN: regime_oracle reads     ║
║    prev_trend from the SHARED published state, so the swap inherits the       ║
║    HL-era trend rather than starting a rival chain. Live divergence <= this.  ║
║                                                                              ║
║ 3. **COVERAGE: 16/16 majors clear the 203-bar gate on Lighter today.**        ║
║    NOTHING is dropped by this swap right now — but the trap is dormant, not   ║
║    absent, and ZEC still shows it twice over: 287 Lighter bars (its entire    ║
║    book) vs HL's 521, clearing the gate by 84 — AND still too young to        ║
║    replay 60 days, so PART 3 could not score it at all. The study measured    ║
║    the same book ungradeable on 115 of 200 days. A coin that clears TODAY     ║
║    and vanished YESTERDAY is what a spot check cannot see; hence the payload  ║
║    field coverage.missing.                                                    ║
║    (Part 2's "HL bars" column is this script's REQUEST depth (300+60+10),     ║
║    not HL's reach — do not read 370 as HL's book age. Only the Lighter        ║
║    counts are book ages, and only where they fall short of the request.)      ║
║                                                                              ║
║ 4. ONE VARIABLE, ASSERTED MECHANICALLY. Both arms are scored by the SAME      ║
║    classify() (the new module's), and this script ASSERTS that classify() +   ║
║    wilder_adx() — and the gates (ADX/EMA/lookback/universe) — are             ║
║    byte-identical between HEAD (still pre-swap) and the working tree. The     ║
║    A/B therefore varies the data source and nothing else. (17-Jul lesson:     ║
║    the Stock Leaders A/B differed three ways and its headline pointed the     ║
║    opposite way to the truth.)                                                ║
║                                                                              ║
║ LIMITATIONS.                                                                  ║
║  * Agreement is not correctness. Nothing here says which source is RIGHT on   ║
║    the 5 days they differ; both are defensible reads of a threshold this      ║
║    oracle makes discontinuous. Ranking them needs calls joined to outcomes.   ║
║  * ONE window (60d) and one live instant. The study's 200d run is the wider   ║
║    prior; this is the shipped-code check that the study could not make.       ║
║  * The replay compares on a common UTC-midnight day grid, so it isolates the  ║
║    SOURCE. Today's-verdict test (1) instead runs each arm's REAL end-to-end   ║
║    path, closed-bar rule included — that is the one that mirrors production.  ║
║  * Coverage counts move as venues list/delist. This is 2026-07-17.            ║
╚══════════════════════════════════════════════════════════════════════════════╝

Read-only: public endpoints only. Touches no bot, no DB, no config.
Needs pandas — run it with the venv interpreter:
    .venv/bin/python scripts/ab_regime_oracle_venue_swap.py
"""
import ast
import json
import os
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402

import regime_oracle as ro  # noqa: E402  (the NEW, shipped module)

HL = "https://api.hyperliquid.xyz/info"
REPLAY_DAYS = 60
DAY = 86400


# ----------------------- the CONTROL arm: the OLD code -----------------------
def old_fetch_daily_hl(coin, days=None):
    """VERBATIM the pre-swap fetch_daily() (git HEAD:regime_oracle.py:63-75),
    parametrised only by lookback so the replay can reach further back. The
    `df.iloc[:-1]` closed-candle rule is the old code's, kept as-is."""
    days = days or ro.LOOKBACK_DAYS
    start = int((time.time() - days * 86400) * 1000)
    body = json.dumps({"type": "candleSnapshot",
                       "req": {"coin": coin, "interval": "1d",
                               "startTime": start}}).encode()
    req = urllib.request.Request(HL, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        rows = json.loads(r.read().decode())
    df = pd.DataFrame(rows)
    for k in ("o", "h", "l", "c"):
        df[k] = df[k].astype(float)
    return df.iloc[:-1]  # closed candles only


def _fn_source(src_text, name):
    """The source segment of a top-level def, straight off the AST."""
    tree = ast.parse(src_text)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.get_source_segment(src_text, node)
    return None


def assert_one_variable():
    """The A/B is only honest if the SCORING code is identical in both arms.
    Prove it: classify() + wilder_adx() must be byte-identical between the
    committed pre-swap module and the working tree.

    NB this is only meaningful while the swap is UNCOMMITTED (git HEAD is still
    the HL version). Once it lands, HEAD == the tree and the check is trivially
    true — it is a guard for the review, not a permanent invariant.
    """
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        old_src = subprocess.check_output(
            ["git", "show", "HEAD:regime_oracle.py"],
            cwd=root, stderr=subprocess.DEVNULL).decode()
    except subprocess.CalledProcessError:
        print("  (could not read HEAD:regime_oracle.py — skipping the "
              "identical-scorer assertion)")
        return
    new_src = open(os.path.join(root, "regime_oracle.py")).read()
    if "api.hyperliquid.xyz" not in old_src:
        print("  (HEAD is already post-swap — the identical-scorer assertion "
              "is trivially true here; it guards the pre-commit review.)\n")
    for fn in ("classify", "wilder_adx"):
        assert _fn_source(old_src, fn) == _fn_source(new_src, fn), (
            f"!!! {fn}() CHANGED between HEAD and the working tree — this A/B "
            f"would vary TWO variables and its headline could not be trusted.")
    for const in ("ADX_TREND", "ADX_CHOP", "EMA_FAST", "LOOKBACK_DAYS",
                  "UNIVERSE"):
        old_v = [ln for ln in old_src.splitlines() if ln.startswith(const)]
        new_v = [ln for ln in new_src.splitlines() if ln.startswith(const)]
        assert old_v == new_v, f"!!! {const} CHANGED: {old_v} -> {new_v}"
    print("  ONE VARIABLE ASSERTED: classify() + wilder_adx() + the gates "
          "(ADX/EMA/lookback/universe) are\n  byte-identical to HEAD — only "
          "the data source differs.\n")


# ------------------------------- day grids -----------------------------------
def grid_from_df(df):
    """the oracle's frame -> {utc_midnight_sec: (o,h,l,c)} (t is ms in both)."""
    out = {}
    for _, r in df.iterrows():
        out[int(r["t"]) // 1000 // DAY * DAY] = (float(r["o"]), float(r["h"]),
                                                 float(r["l"]), float(r["c"]))
    return out


def df_from_grid(grid, upto_ts, win):
    """the <=win closed bars ending at upto_ts — the oracle's real window."""
    ts = sorted(t for t in grid if t <= upto_ts)[-win:]
    return pd.DataFrame({"t": [t * 1000 for t in ts],
                         "o": [grid[t][0] for t in ts],
                         "h": [grid[t][1] for t in ts],
                         "l": [grid[t][2] for t in ts],
                         "c": [grid[t][3] for t in ts]})


def main():
    print("\nREGIME ORACLE — HL(old) vs LIGHTER(new) A/B, on the SHIPPED code")
    print(f"run {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}")
    print(f"module: ADX {ro.ADX_TREND}/{ro.ADX_CHOP} | EMA {ro.EMA_FAST}/"
          f"{ro.EMA_SLOW} | slope {ro.SLOPE_BARS} | lookback {ro.LOOKBACK_DAYS}d"
          f" | gate {ro.EMA_SLOW + ro.SLOPE_BARS} bars | universe "
          f"{len(ro.UNIVERSE)}\n")
    assert_one_variable()

    ids = ro.market_ids()
    deep = ro.LOOKBACK_DAYS + REPLAY_DAYS + 10       # enough for the replay

    # ---- fetch both arms through their REAL paths --------------------------
    print("=" * 78)
    print("PART 1 — TODAY'S VERDICT, each arm's REAL end-to-end path")
    print("=" * 78)
    hdr = (f"{'coin':>5s} {'HLbars':>7s} {'LTbars':>7s} {'HL verdict':>13s} "
           f"{'LT verdict':>13s} {'adxHL':>6s} {'adxLT':>6s} {'same':>5s}")
    print(hdr)
    print("-" * len(hdr))

    today_rows, changed, cov_missing = [], [], {}
    deep_grids = {}
    for coin in ro.UNIVERSE:
        # --- variant: the SHIPPED code, exactly as production calls it ------
        lt_df = lt_err = None
        mid = ids.get(coin)
        if mid is None:
            cov_missing[coin] = "no-lighter-book"
        else:
            try:
                lt_df = ro.fetch_daily(mid)
            except Exception as e:  # noqa: BLE001
                lt_err = f"fetch-failed:{type(e).__name__}"
                cov_missing[coin] = lt_err
        # --- control: the OLD HL code ---------------------------------------
        try:
            hl_df = old_fetch_daily_hl(coin)
        except Exception as e:  # noqa: BLE001
            print(f"{coin:>5s}  HL control fetch failed: {e}")
            continue

        need = ro.EMA_SLOW + ro.SLOPE_BARS
        hl_v = ro.classify(hl_df, None) if len(hl_df) >= need else None
        lt_v = (ro.classify(lt_df, None)
                if lt_df is not None and len(lt_df) >= need else None)
        if lt_df is not None and len(lt_df) < need:
            cov_missing[coin] = f"short-history({len(lt_df)}<{need})"

        same = (hl_v or {}).get("verdict") == (lt_v or {}).get("verdict")
        if not same:
            changed.append((coin, hl_v, lt_v))
        print(f"{coin:>5s} {len(hl_df):>7d} "
              f"{(len(lt_df) if lt_df is not None else 0):>7d} "
              f"{(hl_v or {}).get('verdict', 'SKIP'):>13s} "
              f"{(lt_v or {}).get('verdict', 'SKIP'):>13s} "
              f"{(hl_v or {}).get('adx', float('nan')):>6.1f} "
              f"{(lt_v or {}).get('adx', float('nan')):>6.1f} "
              f"{'yes' if same else 'NO!!':>5s}")
        today_rows.append((coin, hl_v, lt_v))

        # deep grids for the replay (fetched through the shipped pager)
        if mid is not None:
            try:
                keep = ro.LOOKBACK_DAYS
                ro.LOOKBACK_DAYS = deep          # deepen the SHIPPED fetch
                lt_deep = ro.fetch_daily(mid)
                ro.LOOKBACK_DAYS = keep
                hl_deep = old_fetch_daily_hl(coin, days=deep)
                deep_grids[coin] = (grid_from_df(hl_deep), grid_from_df(lt_deep))
            except Exception as e:  # noqa: BLE001
                ro.LOOKBACK_DAYS = keep
                print(f"       ({coin} deep fetch failed: {e})")
        time.sleep(0.25)

    print("-" * len(hdr))
    if changed:
        print("\n  *** BEHAVIOUR CHANGE — THESE COINS' VERDICTS DIFFER TODAY ***")
        for c, a, b in changed:
            print(f"    {c}: HL={(a or {}).get('verdict')} "
                  f"(adx {(a or {}).get('adx')}) -> "
                  f"LT={(b or {}).get('verdict')} (adx {(b or {}).get('adx')})")
        print("  *** THE OPERATOR MUST SEE THIS. Do not ship it silently. ***")
    else:
        print(f"\n  NO VERDICT CHANGES TODAY: {len(today_rows)}/"
              f"{len(ro.UNIVERSE)} majors, every verdict IDENTICAL.")

    # ---- seed invariance: is any coin on the hysteresis knife-edge? --------
    flips = []
    for coin, _hv, _lv in today_rows:
        if coin not in deep_grids:
            continue
        gh, gl = deep_grids[coin]
        last = max(max(gh), max(gl))
        for seed in (None, 0, 1):
            a = ro.classify(df_from_grid(gh, last, ro.LOOKBACK_DAYS), seed)
            b = ro.classify(df_from_grid(gl, last, ro.LOOKBACK_DAYS), seed)
            if a["verdict"] != b["verdict"]:
                flips.append((coin, seed, a["verdict"], b["verdict"]))
    print(f"  SEED INVARIANCE (hysteresis seed None/0/1): "
          + ("ALL AGREE — no major is on the ADX knife-edge today."
             if not flips else f"{len(flips)} seed-dependent split(s): {flips}"))

    # ---- coverage ---------------------------------------------------------
    print("\n" + "=" * 78)
    print("PART 2 — COVERAGE  (a swap that silently drops a coin is a bug)")
    print("=" * 78)
    need = ro.EMA_SLOW + ro.SLOPE_BARS
    print(f"  {'coin':>5s} {'HLbars':>7s} {'LTbars':>7s} {'gate':>6s} "
          f"{'lighter can grade?':>20s}")
    thin = []
    for coin, (gh, gl) in sorted(deep_grids.items()):
        ok = len(gl) >= need
        if not ok:
            thin.append(coin)
        print(f"  {coin:>5s} {len(gh):>7d} {len(gl):>7d} {need:>6d} "
              f"{('yes' if ok else 'NO — WOULD BE SKIPPED'):>20s}")
    if cov_missing:
        print(f"\n  *** COINS LOSING COVERAGE ON LIGHTER: {cov_missing} ***")
        print("      They are NAMED in the payload's coverage.missing — not "
              "silently omitted.")
    else:
        print(f"\n  NO COIN LOSES COVERAGE TODAY: {len(deep_grids)}/"
              f"{len(ro.UNIVERSE)} majors clear the {need}-bar gate on Lighter.")
    if deep_grids:
        floor = min(deep_grids, key=lambda c: len(deep_grids[c][1]))
        print(f"      Thinnest Lighter book: {floor} "
              f"{len(deep_grids[floor][1])} bars (HL {len(deep_grids[floor][0])})"
              f" — clears by {len(deep_grids[floor][1]) - need}. The trap is "
              f"dormant, not absent.")

    # ---- rolling replay ---------------------------------------------------
    print("\n" + "=" * 78)
    print(f"PART 3 — {REPLAY_DAYS}-DAY ROLLING REPLAY (hysteresis per arm, "
          f"common seed)")
    print("=" * 78)
    hdr = (f"{'coin':>5s} {'days':>5s} {'agree':>6s} {'agree%':>7s} "
           f"{'dirX':>5s} {'chrX':>5s}")
    print(hdr)
    print("-" * len(hdr))
    tot = agr = tdir = tchr = 0
    diffs = {}
    for coin, (gh, gl) in sorted(deep_grids.items()):
        common = sorted(set(gh) & set(gl))
        if len(common) < ro.LOOKBACK_DAYS + 5:
            print(f"{coin:>5s}  (too little common history to replay)")
            continue
        days = common[-REPLAY_DAYS:]
        ph = pl = None
        n = a = nd = nc = 0
        for d in days:
            wh = df_from_grid(gh, d, ro.LOOKBACK_DAYS)
            wl = df_from_grid(gl, d, ro.LOOKBACK_DAYS)
            if len(wh) < need or len(wl) < need:
                continue
            vh = ro.classify(wh, ph)
            vl = ro.classify(wl, pl)
            ph, pl = vh["trend"], vl["trend"]
            n += 1
            if vh["verdict"] == vl["verdict"]:
                a += 1
            else:
                if vh["dir"] != vl["dir"]:
                    nd += 1
                if vh["trend"] != vl["trend"]:
                    nc += 1
                diffs.setdefault(coin, []).append((d, vh, vl))
        tot += n
        agr += a
        tdir += nd
        tchr += nc
        pct = 100.0 * a / n if n else float("nan")
        print(f"{coin:>5s} {n:>5d} {a:>6d} {pct:>6.1f}% {nd:>5d} {nc:>5d}")
    print("-" * len(hdr))
    ov = 100.0 * agr / tot if tot else float("nan")
    print(f"{'ALL':>5s} {tot:>5d} {agr:>6d} {ov:>6.1f}% {tdir:>5d} {tchr:>5d}")
    print(f"\n  IDENTICAL ON {ov:.1f}% OF COIN-DAYS ({agr}/{tot}). "
          f"{tot - agr} differ: {tchr} CHARACTER vs {tdir} DIRECTION flips.")
    for c, ds in sorted(diffs.items()):
        print(f"    {c}: " + "; ".join(
            f"{time.strftime('%Y-%m-%d', time.gmtime(d))} "
            f"HL={a['verdict']}(adx{a['adx']:.1f}) LT={b['verdict']}"
            f"(adx{b['adx']:.1f})" for d, a, b in ds[:4]))

    print("\n" + "=" * 78)
    print("BOTTOM LINE")
    print(f"  today   : {'NO CHANGE — all verdicts identical' if not changed else 'CHANGED — SEE ABOVE'}")
    print(f"  {REPLAY_DAYS}d rolling: {ov:.1f}% identical ({agr}/{tot})")
    print(f"  coverage: {'no coin dropped' if not cov_missing else str(cov_missing)}"
          f" (named in coverage.missing either way)")
    print("=" * 78)


if __name__ == "__main__":
    main()
