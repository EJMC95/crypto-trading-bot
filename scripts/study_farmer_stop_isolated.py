#!/usr/bin/env python3
"""
scripts/study_farmer_stop_isolated.py — the STOP 0.10 -> 0.03 decision for the
LIVE Funding Farmer (lighter_funding_bot.py), ISOLATED, on Lighter's own tape.

╔══════════════════════════════════════════════════════════════════════════╗
║ VERDICT (2026-07-21 run, 150d 2026-02-21→07-21, 25 markets, live config   ║
║ gate 0.05 TRUE / TP 0.04 / hold 72h — STOP is the ONLY variable):         ║
║                                                                          ║
║ **THE RULE FAILS — STOP 0.03 DOES NOT SHIP ON THIS EVIDENCE.** It is      ║
║ not-worse than 0.10 (full + both halves) at slip 0, 1.7 and 5 bps/fill,   ║
║ and WORSE at 10 bps/fill (full −41.99 vs −38.61; h2 −3.45 vs +1.50, h2    ║
║ goes NEGATIVE). Mechanism, not noise: 0.03 does 566 more round trips      ║
║ (n 1600 vs 1034; +428 stop-outs, 77→505), so its edge decays 2.83$/bps    ║
║ of per-fill slip; the not-worse crossover is 8.8bps on the full window    ║
║ and **6.6bps on h2 — the binding half**. The verdict therefore DEPENDS on ║
║ the slip term, and Lighter's real round-trip friction is STILL UNMEASURED ║
║ (the entry leg records decision px as fill px — see the harness header).  ║
║ A stop change that flips inside the plausible-friction band is exactly    ║
║ what the pre-stated rule exists to block.                                 ║
║                                                                          ║
║ THE LIVE RECORD AGREES (23 closes, 07-14→07-21, $20 clips): the one real  ║
║ stop (LIT short 07-20, −$2.00 at −10%) becomes ~−$0.60 under 0.03        ║
║ (saves $1.40) — but 7 of the other 22 closes had ≥3% adverse excursions   ║
║ and become NEW stop-outs (four of them were +$0.31..+$0.98 wins that die  ║
║ at −$0.60), net −$4.14, so 0.03 is **−$2.75 net on the record to date**.  ║
║ Per-trade counterfactual only; the true path diverges after the first     ║
║ changed exit.                                                             ║
║                                                                          ║
║ WHAT WOULD SETTLE IT: the measured entry-leg fill (finish the 445e189     ║
║ telemetry). If real round-trip friction ≤ ~5bps/fill total (~2.5bps/leg), ║
║ 0.03 dominates 0.10 everywhere on this tape; if per-fill slip is ~10bps   ║
║ the whole book is −$39..−$44 at EVERY stop and the stop is not the        ║
║ problem. Until then FUNDING_HARD_STOP=0.03 stays where it already is —   ║
║ the shadow A/B arm — and live keeps 0.10.                                 ║
║                                                                          ║
║ REPRO NOTE (honesty about drift): the 17-Jul harness rows (stop 0.10      ║
║ −15.85 / 0.03 +21.32, n=1911 @0.86bps) do NOT reproduce at level today    ║
║ (+8.64 / +31.13, n=1600/1034): the top-25-by-volume universe RE-FORMS at  ║
║ fetch time (SPCX 39d, NBIS 42d, US100 63d, MU 78d are in today's top 25)  ║
║ and the window slid 4d. The DIRECTION is preserved (0.03 beats 0.10 by    ║
║ ~$22 @0.86bps, both runs); the LEVELS are universe-dependent — one more   ║
║ reason not to ship a live change off a single sweep's levels.             ║
║                                                                          ║
║ SINGLE-REGIME CAVEAT: short-carry book (22/23 live closes are shorts) on  ║
║ one falling regime. The bear tape reabsorbs counter-trend rallies, which  ║
║ FLATTERS the wide stop's hold-and-recover thesis — so 0.03 winning the    ║
║ low-slip cells is not the drift's gift. But a rising regime (adverse      ║
║ moves TREND against a short book; 0.03 fires far more often) is           ║
║ unmeasured and unmeasurable on this tape. One-regime evidence only.       ║
╚══════════════════════════════════════════════════════════════════════════╝

WHY THIS EXISTS. `scripts/backtest_funding_lighter.py` (the harness this file
imports and does NOT modify) found the live bot's 10% stop against a 4% TP is
backwards for a mean-reversion book — but its STOP rows were measured at two
frictions only (0.86bps modelled, 5bps assumed), and its own withdrawn-verdict
header proves the friction constant can flip a conclusion. A stop change for a
REAL-MONEY bot must not depend on the unmeasured slip term. So this study holds
the LIVE config fixed (gate 0.05 TRUE, TP 0.04, hold 72h, persist 4h, exit
ratio 0.375, 12h stop cooldown — the harness's mirror of the live bot) and
sweeps EXACTLY ONE variable, the stop, across the whole plausible slip range:

    STOP in {0.10 (live today), 0.05, 0.03}  x  SLIP in {0, 1.7, 5, 10} bps/fill

DECISION RULE (stated before the data was seen): STOP 0.03 ships ONLY if it is
not-worse than 0.10 on the FULL window AND BOTH halves at EVERY slip level
tested. One failing cell = do not ship on this evidence.

MECHANICAL NOTE that makes the slip sweep exact: in the harness, SLIP enters
P&L only (pp = raw*ntl - 2*SLIP*ntl) and never the entry/exit path, so n and
the exit mix are identical across slip levels for a given stop. The table
prints them once per stop and the script asserts it.

ALSO MEASURED, from the live record (dashboard /trades.json?source=paper,
fetched at run time): the one real stop the live book has taken vs what a 0.03
stop would have done on the same tape, and how many of the OTHER live closes
would have become stop-outs under 0.03 (a tighter stop fires more often — the
trade-off is quantified, not waved at). Per-trade counterfactual only: an early
stop frees a slot and starts a 12h cooldown, so the true path diverges after
the first changed exit — stated, not hidden.

SINGLE-REGIME CAVEAT (doctrine, 21-Jul review item 18): this is a SHORT-carry
book (positive funding -> the farmer shorts; the live record is ~all shorts)
measured on ONE falling regime. A falling tape is the regime MOST favourable
to the WIDE stop's hold-and-recover thesis — adverse moves on a short book are
counter-trend rallies, which this regime tends to reabsorb, and runaway rallies
(the wide stop's tail risk) are rarest here. So on the whipsaw axis the tape
flatters 0.10, not 0.03 — a 0.03 win here is not the drift's gift. But the
converse is unmeasured: in a RISING regime a short book's adverse moves TREND,
0.03 would fire far more often, and no both-halves pass in that regime exists
or can exist on this tape. One-regime pass, in that regime only.

SHIP MECHANICS if the rule passes (from lighter_funding_bot.py's own header):
FUNDING_HARD_STOP=0.03 is already the shadow A/B arm; promotion goes through
the experiment judge's paired bar or an explicit operator env flip — and NEVER
tighten a live stop with positions open (next loop it liquidates anything
already >3% adverse).

Read-only: hits Lighter's public endpoints (through the harness's fetchers,
wrapped with a polite inter-request sleep) + the dashboard's no-auth trades
endpoint. Writes only the harness's own cache. Touches no bot, no DB.
    python3 scripts/study_farmer_stop_isolated.py                # 150d, top 25
    python3 scripts/study_farmer_stop_isolated.py --days 150 --refresh
"""
import argparse
import json
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backtest_funding_lighter as H   # the harness — imported, never modified

DASH = "https://pnl-dashboard-production-858c.up.railway.app"
LIVE_BOT = "perps-funding-lighter-lighter"
GATE = 0.05                      # live today (0.40 published / 8)
STOPS = [0.10, 0.05, 0.03]       # 0.10 = live today
SLIPS_BPS = [0.0, 1.7, 5.0, 10.0]
REPRO_BPS = 0.86                 # the shadow-model friction the 17-Jul rows used

# ---- polite paging: wrap the harness's fetcher, don't modify it -------------
_orig_get = H._get
def _polite_get(path, **q):
    time.sleep(0.15)
    return _orig_get(path, **q)
H._get = _polite_get


def run_cfg(mk, stop, slip_bps, t0, t1):
    H.HARD_STOP = stop
    H.SLIP = slip_bps / 1e4
    return H.run(mk, GATE, t0, t1)


def fetch_live_trades():
    url = DASH + "/trades.json?source=paper"
    with urllib.request.urlopen(url, timeout=60) as r:
        d = json.loads(r.read())
    return [t for t in d.get("trades", []) if t.get("bot") == LIVE_BOT
            and t.get("closed_at") and t.get("entry_price")]


def live_counterfactuals(trades, mk, days):
    """Per-trade: max adverse excursion before the ACTUAL close, and what a
    0.03 stop would have done (harness conventions: stop checked from the bar
    AFTER entry, on intrabar hi/lo; exit at entry*(1±0.03); funding accrued
    hourly at the settled rate to the stop bar; zero-slip $ shown — slip is
    the same round trip under either stop, so it cancels in the comparison)."""
    import calendar
    # market_id lookup for pairs outside the backtest universe
    need = {t["pair"] for t in trades} - set(mk)
    extra = {}
    if need:
        obs = H._get("/api/v1/orderBookDetails").get("order_book_details") or []
        m_id = {o["symbol"]: o["market_id"] for o in obs if o.get("symbol")}
        for sym in sorted(need):
            if sym not in m_id:
                print(f"  {sym}: no market id — skipped")
                continue
            extra[sym] = {"fund": H.fetch_fundings(m_id[sym], days),
                          "cand": H.fetch_candles(m_id[sym], days)}
    out = []
    for t in trades:
        sym = t["pair"]
        m = mk.get(sym) or extra.get(sym)
        if not m:
            continue
        def ts(s):
            return calendar.timegm(time.strptime(s[:19], "%Y-%m-%dT%H:%M:%S"))
        t_in, t_out = ts(t["opened_at"]), ts(t["closed_at"])
        px, short = float(t["entry_price"]), t["side"] == "short"
        ntl = abs(t["pnl_abs"] / t["pnl_pct"]) if t.get("pnl_pct") else 20.0
        h0 = (t_in // 3600) * 3600
        stop3_px = px * (1.03 if short else 0.97)
        max_adv, stop3_t, fund3 = 0.0, None, 0.0
        for hb in range(h0 + 3600, ((t_out // 3600) + 1) * 3600 + 1, 3600):
            c = m["cand"].get(hb)
            apr = m["fund"].get(hb)
            if apr is not None and stop3_t is None:
                fund3 += (1.0 if short else -1.0) * (apr / (24 * 365)) * ntl
            if c is None:
                continue
            _o, hi, lo, _c = c
            adv = (hi - px) / px if short else (px - lo) / px
            max_adv = max(max_adv, adv)
            if stop3_t is None and adv >= 0.03:
                stop3_t = hb
        cf_pnl = (-0.03 * ntl + fund3) if stop3_t else None
        out.append({"trade": t, "ntl": ntl, "max_adv": max_adv,
                    "stop3_t": stop3_t, "stop3_px": stop3_px,
                    "cf_pnl": cf_pnl, "fund3": fund3,
                    "held_h": (t_out - t_in) / 3600.0})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=150)
    ap.add_argument("--universe", type=int, default=25)
    ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args()

    print(f"Fetching LIGHTER history via the harness — {a.days}d, "
          f"top {a.universe} by daily quote volume (polite paging)")
    mk = H.load(a.days, a.universe, a.refresh)
    if not mk:
        raise SystemExit("no markets with paired funding+candle history")
    hours = sorted({t for m in mk.values() for t in m["fund"]})
    lo, hi = min(hours), max(hours)
    mid = lo + (hi - lo) // 2
    print(f"\n{len(mk)} markets | {time.strftime('%Y-%m-%d', time.gmtime(lo))} -> "
          f"{time.strftime('%Y-%m-%d', time.gmtime(hi))} ({(hi-lo)/86400:.0f}d)")
    print(f"LIVE config held fixed: gate {GATE:.2f} TRUE | TP {H.TAKE_PROFIT:.2f} | "
          f"hold {H.MAX_HOLD_H}h | persist {H.PERSIST_H}h | exit ratio {H.EXIT_RATIO} | "
          f"clip ${H.ORDER_USD:.0f} x {H.MAX_OPEN} slots\n")

    # ---- the STOP-ISOLATED table -------------------------------------------
    res = {}
    for stop in STOPS:
        for s in SLIPS_BPS + [REPRO_BPS]:
            res[(stop, s)] = (run_cfg(mk, stop, s, lo, hi + 1),
                              run_cfg(mk, stop, s, lo, mid),
                              run_cfg(mk, stop, s, mid, hi + 1))
    # slip never touches the path — assert it, then print n/stop-mix once per stop
    for stop in STOPS:
        ns = {res[(stop, s)][0]["n"] for s in SLIPS_BPS}
        assert len(ns) == 1, f"slip changed the path at stop {stop}: {ns}"

    hdr = (f"{'STOP':>5s} {'slip':>5s} | {'P&L $':>8s} {'n':>5s} {'win%':>5s} "
           f"{'stop n':>6s} {'stop $':>8s} {'$/stop':>7s} | "
           f"{'h1 $':>8s} {'h2 $':>8s} {'h1/h2 stop n':>12s}")
    print(hdr); print("-" * len(hdr))
    for stop in STOPS:
        for s in SLIPS_BPS:
            f, h1, h2 = res[(stop, s)]
            sn, sp = f["why_n"].get("stop", 0), f["why_pnl"].get("stop", 0.0)
            tag = "  <- LIVE TODAY" if (stop == 0.10 and s == 0.0) else ""
            print(f"{stop:>5.2f} {s:>5.1f} | {f['pnl']:>8.2f} {f['n']:>5d} "
                  f"{f['win']:>5.1f} {sn:>6d} {sp:>8.2f} "
                  f"{(sp/sn if sn else 0.0):>7.2f} | "
                  f"{h1['pnl']:>8.2f} {h2['pnl']:>8.2f} "
                  f"{h1['why_n'].get('stop',0):>5d}/{h2['why_n'].get('stop',0):<5d}{tag}")
        print()

    # ---- reproduction check vs the 17-Jul harness rows ----------------------
    print(f"repro @{REPRO_BPS}bps (17-Jul harness header said stop 0.10 -> -15.85, "
          f"0.03 -> +21.32, n=1911; window has since slid ~4d):")
    for stop in (0.10, 0.03):
        f, h1, h2 = res[(stop, REPRO_BPS)]
        print(f"  stop {stop:.2f}: {f['pnl']:>8.2f}  n={f['n']}  "
              f"h1 {h1['pnl']:.2f} / h2 {h2['pnl']:.2f}")

    # ---- decision rule ------------------------------------------------------
    print("\nDECISION RULE — 0.03 ships ONLY if not-worse than 0.10 on full window "
          "AND both halves at EVERY slip level:")
    all_pass = True
    for s in SLIPS_BPS:
        f3, h13, h23 = res[(0.03, s)]
        f0, h10, h20 = res[(0.10, s)]
        ok = (f3["pnl"] >= f0["pnl"] and h13["pnl"] >= h10["pnl"]
              and h23["pnl"] >= h20["pnl"])
        all_pass &= ok
        print(f"  slip {s:>4.1f}bps: full {f3['pnl']:>8.2f} vs {f0['pnl']:>8.2f} | "
              f"h1 {h13['pnl']:>7.2f} vs {h10['pnl']:>7.2f} | "
              f"h2 {h23['pnl']:>7.2f} vs {h20['pnl']:>7.2f}  -> "
              f"{'not-worse' if ok else 'WORSE — FAIL'}")
    extra_stops = (res[(0.03, 0.0)][0]["why_n"].get("stop", 0)
                   - res[(0.10, 0.0)][0]["why_n"].get("stop", 0))
    print(f"\n  additional stop-outs 0.03 creates on this window: +{extra_stops} "
          f"({res[(0.10,0.0)][0]['why_n'].get('stop',0)} -> "
          f"{res[(0.03,0.0)][0]['why_n'].get('stop',0)})")
    print(f"  RULE {'PASSES — 0.03 not-worse at every slip tested' if all_pass else 'FAILS — do not ship on this evidence'}")

    # ---- the live record ----------------------------------------------------
    print("\n=== LIVE RECORD (dashboard ledger, fetched now) ===")
    try:
        trades = fetch_live_trades()
    except Exception as e:
        trades = []
        print(f"  ledger fetch failed ({e}) — live section skipped")
    if trades:
        print(f"  {len(trades)} closed live trades visible in the ledger window")
        cfs = live_counterfactuals(trades, mk, 14)   # live record spans <14d
        stops = [c for c in cfs if c["trade"]["reason"].endswith("_stop")]
        would = [c for c in cfs if not c["trade"]["reason"].endswith("_stop")
                 and c["stop3_t"] is not None]
        for c in stops:
            t = c["trade"]
            print(f"\n  the real stop: {t['pair']} {t['side']} entered "
                  f"{t['opened_at'][:16]}Z @ {t['entry_price']}, stopped @ "
                  f"{t['exit_price']} after {c['held_h']:.1f}h = ${t['pnl_abs']:+.2f}")
            if c["stop3_t"]:
                print(f"    under 0.03: stopped at "
                      f"{time.strftime('%m-%d %H:%M', time.gmtime(c['stop3_t']))}Z "
                      f"@ ~{c['stop3_px']:.4f} for ~${c['cf_pnl']:+.2f} "
                      f"(price -3.00% = ${-0.03*c['ntl']:.2f}, funding to that bar "
                      f"${c['fund3']:+.2f}; zero-slip; slip cancels between the two stops)"
                      f" -> saves ~${c['cf_pnl'] - t['pnl_abs']:+.2f}")
        print(f"\n  additional live closes a 0.03 stop would have converted to "
              f"stop-outs: {len(would)} of {len(cfs) - len(stops)}")
        for c in would:
            t = c["trade"]
            print(f"    {t['pair']:>5s} {t['side']:>5s} {t['opened_at'][:16]}Z  "
                  f"max adverse {c['max_adv']*100:>5.2f}%  actual "
                  f"{t['reason']:>17s} ${t['pnl_abs']:+.2f}  ->  0.03 stop "
                  f"~${c['cf_pnl']:+.2f}  (delta ${c['cf_pnl']-t['pnl_abs']:+.2f})")
        if would or stops:
            d_stop = sum(c["cf_pnl"] - c["trade"]["pnl_abs"] for c in stops if c["cf_pnl"] is not None)
            d_would = sum(c["cf_pnl"] - c["trade"]["pnl_abs"] for c in would)
            print(f"\n  net per-trade counterfactual on the visible live record: "
                  f"${d_stop + d_would:+.2f} (stop saved ${d_stop:+.2f}, "
                  f"new stop-outs cost ${d_would:+.2f}). Per-trade only — the real "
                  f"path diverges after the first changed exit (slot + 12h cooldown).")

    print("\nSINGLE-REGIME CAVEAT: short-carry book, one falling regime (the whole "
          "438d Lighter tape is bear; both halves fall). A bear tape reabsorbs the "
          "counter-trend rallies that hit a short book, which FLATTERS the wide "
          "stop's hold-and-recover thesis — so a 0.03 win here is not the drift's "
          "gift. But a RISING regime (where a short book's adverse moves trend and "
          "0.03 fires far more often) is unmeasured and unmeasurable on this tape. "
          "One-regime pass, in that regime only.")
    print("\nSHIP MECHANICS: promotion via the experiment judge's paired bar "
          "(FUNDING_HARD_STOP=0.03 is already the shadow A/B arm) or an explicit "
          "operator env flip — and NEVER tighten a live stop with positions open.")


if __name__ == "__main__":
    main()
