#!/usr/bin/env python3
"""
brain_replay.py — validate the brain's v3 statistics engine against v2 by
replaying the REAL trade ledger through the REAL qualification code
(bot_learn.compute_stake_mults with engine forced — the
lighter_ticket_replay pattern: rule changes judged in seconds, not
shadow-days).

WHAT IT DOES
  1. Fetches both ledgers over HTTP (bot_trades + paper_trades via the
     dashboard's /trades.json — no DATABASE_URL needed on a laptop).
  2. Simulates a brain run every 2h across the ledger window. At each run
     T, every bot alive at T (>=1 close, last close within 7d of T) is
     graded on its era trades closed by T — v2 and v3 run side by side
     with SEPARATE streak states, exactly as the production code would.
  3. Counterfactual: every era trade is scaled by the multiplier in force
     at its OPEN under each policy (last publish before open, within TTL).
     saved$ = (1 - mult) * (-pnl): positive when the throttle dodged a
     loss, negative when it forfeited a win (false throttle).
  4. Scores both policies overall, on BOTH TIME HALVES (validation
     doctrine), and per-(bot, tag); sweeps the v3 half-life.

ANACHRONISM NOTE: the current RETIRED_BOTS list is NOT applied — mid-
window those bots were alive and are exactly the biggest tagged samples
(rsi-meanrev n=128, donchian n=112). Liveness is applied AT SIM TIME
(7d close recency), the same rule the brain runs today.

VERDICT (run 2026-07-16, ledger 2026-07-03..07-15, 763 closed era trades,
19 bots): PASS.
  LEDGER LEG — no-regression: ZERO (bot, tag) buckets qualify under
  EITHER engine on this window. The post-pivot tagged sleeves are mostly
  positive (rsi-meanrev|long +$68.88 @ 70% wr; donchian|long +$272.09 @
  88%) and ERA_START correctly excludes the old bleeders, so there is
  legitimately nothing to throttle — and, crucially, v3 invents NO
  spurious throttles where v2 has none (the false-positive risk of a new
  statistics engine). crypto-trend-daily|sma_fast_above_slow (0-for-12,
  t=-10.9) is below both engines' floors; v3 surfaces it on the vitals
  WATCHLIST instead. Half-life sweep 7/14/28d: identical (zero throttles).
  SYNTHETIC LEG — discrimination (all PASS):
    A persistent bleeder: both engines 0.5x, v3 not slower (day 3.7 both)
    B healed bleeder:     v2 throttles forever on raw totals; v3's decay
                          releases it once the tag trades clean
    C small noisy sample: neither fires (floors hold)
    D pooling rescue:     v2 soft-throttles 16 noisy trades; v3 blocked
                          by strongly-positive tag siblings (n_eff 50)
    E pooling condemn:    both fire — the family-condemn path lowers the
                          t bar to -0.5 when the family (n_eff>=30) is
                          itself bad (mu<0.30); own EV still required
    F flash collapse:     v3's EMERGENCY fast-path (EMER_* bars, 16-Jul
                          "no-brainer window") publishes on the FIRST
                          qualifying run (day 6.29) while v2 waits out
                          the 3-run streak (6.38); trickle bleeders (A)
                          correctly get NO fast-path
  => v3 SHIPPED as default engine; BRAIN_MULT_ENGINE=v2 remains the
  kill switch.

ADDENDUM (2026-07-23): the 16-Jul verdict validated only the REDUCE half —
`score()` dropped every `m >= 1.0`, so the two-way EXPAND direction (shipped
21-Jul) had ZERO harness coverage and this VERDICT predated it. Now covered
BOTH ways, and runnable OFFLINE via `--selftest` (registered in
tests/test_selftests.py, so the widen direction is under continuous test, not
just this network-requiring main()):
  H strong winner:  v3 EXPANDS a clean n=40 / ~90%-wr bucket to 1.5x (EXP_HARD
                    bars); v2 has no expand path -> the discrimination. score()
                    books it as gained>0 (amplified wins), never a reduce.
  I thin winner:    the SAME 90%-wr shape at n=20 < the full-30 expand floor —
                    v3 REFUSES to widen (no soft-n path). The brake that stops
                    the widen direction acting before it has the evidence.
The ledger LEG still needs a fresh online run to re-attest no-regression with
expand armed; the SYNTHETIC leg (A-I) is green offline.
"""
import json
import sys
import urllib.request
from collections import defaultdict

import bot_learn
import brain_stats  # noqa: F401  (bot_learn dispatches through it)

BASE = "https://pnl-dashboard-production-858c.up.railway.app"
RUN_EVERY_SEC = 7200
TTL = bot_learn.MULT_TTL_SEC
LIVENESS_SEC = bot_learn.LIVENESS_DAYS * 86400


def fetch(url):
    with urllib.request.urlopen(url, timeout=30) as r:
        d = json.loads(r.read().decode())
    return d if isinstance(d, list) else d.get("trades", d.get("data", []))


def load_trades():
    """bot_trades rows come freqtrade-shaped; the HTTP paper feed is RAW
    paper_trades schema, so normalize it exactly like
    bot_pnl_store.fetch_paper_trades does for the production brain
    (skip-row filter, pnl_abs->profit_abs, split_reason -> enter_tag)."""
    from bot_pnl_store import split_reason
    trades = fetch(BASE + "/trades.json?limit=2000")
    for p in fetch(BASE + "/trades.json?limit=5000&source=paper"):
        if not isinstance(p, dict) or p.get("side") == "skip":
            continue
        direction, exit_reason = split_reason(p.get("reason"))
        trades.append({
            "bot": p.get("bot"), "pair": p.get("pair"),
            "profit_abs": float(p["pnl_abs"]) if p.get("pnl_abs") is not None else 0.0,
            "profit_ratio": p.get("pnl_pct"),
            "enter_tag": direction or None,
            "exit_reason": exit_reason or "trade",
            "open_ts": p.get("opened_at"), "close_ts": p.get("closed_at"),
            "is_open": False,
        })
    out = []
    for t in trades:
        if not isinstance(t, dict) or t.get("is_open"):
            continue
        t["_close_epoch"] = bot_learn._epoch(t.get("close_ts"))
        t["_open_epoch"] = bot_learn._epoch(t.get("open_ts"))
        if t["_close_epoch"] and t["_open_epoch"]:
            out.append(t)
    return out


def era_filter(trades):
    out = []
    for t in trades:
        era = bot_learn.ERA_START.get(t.get("bot"))
        if era and str(t.get("open_ts") or "") < era:
            continue
        out.append(t)
    return out


def trio_cards(by_bot_closed):
    cards = {}
    for bot, trs in by_bot_closed.items():
        by_tag = defaultdict(lambda: {"n": 0, "w": 0, "pnl": 0.0})
        for t in trs:
            tag = str(t.get("enter_tag") or "(untagged)")
            b = by_tag[tag]
            b["n"] += 1
            b["pnl"] += t.get("profit_abs") or 0.0
            if (t.get("profit_abs") or 0) > 0:
                b["w"] += 1
        cards[bot] = {"by_tag": dict(by_tag)}
    return cards


def simulate(trades, engine, half_life=None):
    """Returns (timeline [(T, {(bot,tag): mult})], n_runs)."""
    if half_life is not None:
        bot_learn.HALF_LIFE_DAYS = half_life
    t0 = min(t["_close_epoch"] for t in trades)
    t1 = max(t["_close_epoch"] for t in trades)
    state, timeline, run_no = {}, [], 0
    T = t0 + RUN_EVERY_SEC
    while T <= t1 + RUN_EVERY_SEC:
        run_no += 1
        closed = [t for t in trades if t["_close_epoch"] <= T]
        by_bot = defaultdict(list)
        for t in closed:
            by_bot[t.get("bot", "?")].append(t)
        alive = {b: trs for b, trs in by_bot.items()
                 if T - max(x["_close_epoch"] for x in trs) <= LIVENESS_SEC}
        pub, _ = bot_learn.compute_stake_mults(
            trio_cards(alive), state, run_no,
            era_trades=alive, now_ts=T, engine=engine)
        snap = {(b, tag): m["mult"] for b, tags in pub.items()
                for tag, m in tags.items()}
        timeline.append((T, snap))
        T += RUN_EVERY_SEC
    return timeline, run_no


def mult_at(timeline, bot, tag, when):
    m = 1.0
    for T, snap in timeline:
        if T > when:
            break
        if when - T <= TTL:
            m = snap.get((bot, tag), 1.0)
        else:
            m = 1.0
    return m


def score(trades, timeline):
    saved = h1 = h2 = forgone = 0.0
    throttled = 0
    # [2026-07-23 EXPAND-SIDE ACCOUNTING] the two-way WIDEN direction (shipped
    # 21-Jul) was INVISIBLE to this harness: the old `if m >= 1.0: continue`
    # dropped every expansion, so brain_replay validated only the REDUCE half
    # and its VERDICT predated the expand feature by 5 days. Expand is now
    # scored in a PARALLEL set of metrics — the reduce accounting below is
    # byte-identical (m<1 branch), so the ledger no-regression and the A-F/G
    # assertions are unchanged. Same sign convention both ways: s>0 = the mult
    # HELPED (reduce dodged a loss / expand amplified a win), s<0 = it HURT
    # (reduce forfeited a win / expand amplified a loss).
    expanded = 0
    gained = eh1 = eh2 = squandered = 0.0
    per_bucket = defaultdict(lambda: {"trades": 0, "saved": 0.0})
    mid = (min(t["_open_epoch"] for t in trades)
           + max(t["_open_epoch"] for t in trades)) / 2.0
    for t in trades:
        tag = str(t.get("enter_tag") or "(untagged)")
        if tag == "(untagged)":
            continue
        m = mult_at(timeline, t.get("bot"), tag, t["_open_epoch"])
        if m == 1.0:
            continue
        pnl = t.get("profit_abs") or 0.0
        s = (1.0 - m) * (-pnl)
        first_half = t["_open_epoch"] <= mid
        if m < 1.0:                          # REDUCE — accounting unchanged
            throttled += 1
            saved += s
            if s < 0:
                forgone += s
            if first_half:
                h1 += s
            else:
                h2 += s
            k = f"{t.get('bot')}|{tag}"
            per_bucket[k]["trades"] += 1
            per_bucket[k]["saved"] += s
        else:                                # EXPAND (m > 1.0) — new accounting
            expanded += 1
            gained += s
            if s < 0:
                squandered += s
            if first_half:
                eh1 += s
            else:
                eh2 += s
    return {"throttled": throttled, "saved": saved, "h1": h1, "h2": h2,
            "forgone": forgone, "buckets": dict(per_bucket),
            "expanded": expanded, "gained": gained, "eh1": eh1, "eh2": eh2,
            "squandered": squandered}


# ---------------------------------------------------------------------------
# Synthetic discrimination suite. The real 3->15 Jul window produced ZERO
# qualifying buckets under BOTH engines (post-pivot tagged sleeves are
# positive; ERA_START correctly excludes the old bleeders), so the live
# ledger validates NO-REGRESSION (v3 invents no spurious throttles) but
# cannot discriminate the engines. These deterministic scenarios encode the
# exact behaviors v3 claims; each is asserted PASS/FAIL below.
# ---------------------------------------------------------------------------

def _syn(bot, tag, t0, specs):
    """specs: [(day_offset, pnl), ...] -> synthetic closed trades (1h holds)."""
    out = []
    for day, pnl in specs:
        o = t0 + day * 86400
        out.append({"bot": bot, "pair": "SYN/USD", "enter_tag": tag,
                    "exit_reason": "syn", "profit_abs": pnl,
                    "profit_ratio": pnl / 100.0, "is_open": False,
                    "open_ts": "", "close_ts": "",
                    "_open_epoch": o, "_close_epoch": o + 3600})
    return out


def synthetic_scenarios(t0):
    """Returns (trades, checks). checks: (name, bot, tag, expect_fn) where
    expect_fn(end_mult_v2, end_mult_v3, first_v2, first_v3) -> (ok, note)."""
    S = []
    # A. persistent bleeder: 40 trades over 10d, wr 15%, clearly negative.
    S += _syn("syn-bleeder", "long-syn",
              t0, [(d * 0.25, (1.0 if i % 7 == 0 else -2.0))
                   for i, d in enumerate(range(40))])
    # B. healed bleeder: 25 losses days 0-3, then 15 winners days 8-12.
    #    Raw: n=40, wr=15/40=37.5%, pnl -25*2+15*1.5=-27.5 -> v2 holds 0.75x
    #    forever; decayed EV flips positive -> v3 releases.
    S += _syn("syn-healed", "long-syn2",
              t0, [(d * 0.12, -2.0) for d in range(25)]
              + [(8 + d * 0.27, 1.5) for d in range(15)])
    # C. noisy small sample: 12 trades, wr 25%, mildly negative -> floors
    #    hold for BOTH engines.
    S += _syn("syn-noisy", "long-syn3",
              t0, [(d * 0.8, (1.2 if i % 4 == 0 else -0.5))
                   for i, d in enumerate(range(12))])
    # D. pooling rescue: target 16 trades wr ~19% mildly negative (v2 soft
    #    rule fires) while two siblings run the SAME tag strongly positive
    #    (n=25 each, wr 72%) -> v3's tag-family prior blocks the throttle.
    S += _syn("syn-poolA", "long-pool",
              t0, [(d * 0.6, (1.0 if i % 5 == 0 else -0.4))
                   for i, d in enumerate(range(16))])
    for sib in ("syn-poolB", "syn-poolC"):
        S += _syn(sib, "long-pool",
                  t0, [(d * 0.4, (1.0 if i % 4 else -0.6))
                       for i, d in enumerate(range(25))])
    # E. pooling condemn: same target shape, but siblings are ALSO bleeding
    #    -> the prior confirms and v3 fires alongside v2.
    S += _syn("syn-condA", "long-cond",
              t0, [(d * 0.6, (1.0 if i % 5 == 0 else -0.4))
                   for i, d in enumerate(range(16))])
    for sib in ("syn-condB", "syn-condC"):
        S += _syn(sib, "long-cond",
                  t0, [(d * 0.4, (0.8 if i % 5 == 0 else -0.7))
                       for i, d in enumerate(range(25))])
    # F. flash collapse: 20 harmless trades over 6 days, then 25 straight
    #    losses inside half a day. v2 qualifies but waits out the 3-run
    #    streak; v3's EMERGENCY fast-path (n>=40, t<=-2.5, post_wr<0.20)
    #    publishes on the first qualifying run. (Loss spacing 0.016d =
    #    23min > the 10-min episode gap — a flash CASCADE of distinct
    #    closes, deliberately NOT one burst; G below covers bursts.)
    S += _syn("syn-flash", "long-flash",
              t0, [(d * 0.3, (1.0 if i % 3 == 0 else -0.1))
                   for i, d in enumerate(range(20))]
              + [(6.0 + i * 0.016, -2.0) for i in range(25)])

    def c(name, bot, tag, fn):
        return (name, bot, tag, fn)
    checks = [
        c("A bleeder throttled by BOTH, v3 not slower", "syn-bleeder", "long-syn",
          lambda e2, e3, f2, f3: (e2 is not None and e3 is not None
                                  and (f3 or 9e18) <= (f2 or 9e18),
                                  f"end v2={e2} v3={e3}, first v2={f2} v3={f3}")),
        c("B healed: v2 still throttling, v3 released", "syn-healed", "long-syn2",
          lambda e2, e3, f2, f3: (e2 is not None and e3 is None,
                                  f"end v2={e2} v3={e3}")),
        c("C small noisy: NEITHER fires (floors)", "syn-noisy", "long-syn3",
          lambda e2, e3, f2, f3: (f2 is None and f3 is None, f"first v2={f2} v3={f3}")),
        c("D pooling rescue: v2 fires, v3 blocked by siblings", "syn-poolA", "long-pool",
          lambda e2, e3, f2, f3: (f2 is not None and f3 is None,
                                  f"first v2={f2} v3={f3}")),
        c("E pooling condemn: BOTH fire", "syn-condA", "long-cond",
          lambda e2, e3, f2, f3: (f2 is not None and f3 is not None,
                                  f"first v2={f2} v3={f3}")),
        c("F flash collapse: v3 fast-path beats v2's streak wait", "syn-flash", "long-flash",
          lambda e2, e3, f2, f3: (f2 is not None and f3 is not None and f3 < f2,
                                  f"first v2={f2} v3={f3}")),
    ]
    return S, checks


def synthetic_scenarios_isolated(t0):
    """[2026-07-22] Scenarios that must run in their OWN universe. The
    global fleet prior pools EVERY bucket in a simulate() pass, so adding
    a bucket to the A-F universe moves their priors — measured while
    adding G: its positive episode win rate nudged the fleet mu enough to
    cross F's EMER_POST_WR knife-edge and cost the fast-path its latency
    win. A-F stay byte-identical to the validated 16-Jul universe; each
    entry here is a (trades, checks) universe simulated separately.

    G. correlated burst (the (bb) deferred item, built 22-Jul): the same
       loss dollars as a condemnable bleeder, arriving as 3 same-minute
       multi-fill bursts (the recorded dad+breakout-4h shape: "identical
       pairs closed within 4 minutes"). Raw counts read n=40 wr 17.5%
       -$59 -> v2 fires; the episode basis reads 3 loss EVENTS among 10
       episodes and must refuse — 10 fills of one dump are not 10 units
       of evidence."""
    G = _syn("syn-burst", "long-burst",
             t0, [(3.0 + b * 2 + i * 0.002, -2.0)
                  for b in range(3) for i in range(11)]
             + [(d * 0.9, 1.0) for d in range(7)])
    g_check = [("G correlated burst: v2 raw-counts fire, v3 episode basis "
                "refuses", "syn-burst", "long-burst",
                lambda e2, e3, f2, f3: (f2 is not None and f3 is None,
                                        f"first v2={f2} v3={f3}"))]
    # H. genuine strong winner — the EXPAND direction's POSITIVE case (23-Jul,
    #    the widen half the 21-Jul two-way ship added and this harness never
    #    tested). 40 trades over 10d, ~90% wr, winners +2.0 / losers -1.0: n
    #    clears the full-30 expand floor and post_wr / Wilson-lo / t all pass
    #    the 1.5x mirror bars (EXP_HARD_*), so v3 EXPANDS. v2 has NO expand
    #    path, so it does nothing — the discrimination.
    H = _syn("syn-strong", "long-strong",
             t0, [(d * 0.25, (2.0 if i % 10 else -1.0))
                  for i, d in enumerate(range(40))])
    h_check = [("H strong winner: v3 EXPANDS (>1x), v2 has no expand path",
                "syn-strong", "long-strong",
                lambda e2, e3, f2, f3: (e2 is None and e3 is not None
                                        and e3 > 1.0,
                                        f"end v2={e2} v3={e3}"))]
    # I. strong but THIN — the floor GUARD (the brake that stops the widen
    #    direction acting before it has the sample). SAME 90%-wr shape at n=20
    #    < the full-30 expand floor. Expand has no soft-n path, so v3 must
    #    REFUSE to widen; v2 does nothing either. A widen that fired here would
    #    be exactly the "authority without evidence" failure to avoid.
    I = _syn("syn-thin", "long-thin",
             t0, [(d * 0.4, (2.0 if i % 10 else -1.0))
                  for i, d in enumerate(range(20))])
    i_check = [("I thin winner: v3 REFUSES to expand (full-30 floor holds)",
                "syn-thin", "long-thin",
                lambda e2, e3, f2, f3: (e2 is None and e3 is None,
                                        f"end v2={e2} v3={e3}"))]
    return [(G, g_check), (H, h_check), (I, i_check)]


def bucket_timeline(timeline, bot, tag):
    """(first_throttle_T, end_mult) for one (bot, tag)."""
    first, end = None, None
    for T, snap in timeline:
        m = snap.get((bot, tag))
        if m is not None and first is None:
            first = T
        end = snap.get((bot, tag))
    return first, end


def run_synthetic_suite(t0):
    """Run the synthetic discrimination suite (A-F pooled + G/H/I isolated)
    against t0. Returns (ok, lines). Fully OFFLINE — no ledger fetch — so
    `--selftest` and the test harness can exercise BOTH directions (reduce AND
    the 21-Jul expand) without network; main() reuses it after the fetch."""
    lines = []
    rel = lambda f: None if f is None else round((f - t0) / 86400.0, 2)
    syn_trades, checks = synthetic_scenarios(t0)
    syn_tl = {}
    for engine in ("v2", "v3"):
        syn_tl[engine], _ = simulate(syn_trades, engine, half_life=14.0)
    syn_ok = True
    for name, bot, tag, fn in checks:
        f2, e2 = bucket_timeline(syn_tl["v2"], bot, tag)
        f3, e3 = bucket_timeline(syn_tl["v3"], bot, tag)
        ok, note = fn(e2, e3, rel(f2), rel(f3))
        syn_ok &= bool(ok)
        lines.append(f"  [{'PASS' if ok else 'FAIL'}] {name}  ({note})")
    # isolated universes (see synthetic_scenarios_isolated's docstring)
    for iso_trades, iso_checks in synthetic_scenarios_isolated(t0):
        iso_tl = {}
        for engine in ("v2", "v3"):
            iso_tl[engine], _ = simulate(iso_trades, engine, half_life=14.0)
        for name, bot, tag, fn in iso_checks:
            f2, e2 = bucket_timeline(iso_tl["v2"], bot, tag)
            f3, e3 = bucket_timeline(iso_tl["v3"], bot, tag)
            ok, note = fn(e2, e3, rel(f2), rel(f3))
            syn_ok &= bool(ok)
            lines.append(f"  [{'PASS' if ok else 'FAIL'}] {name}  ({note})")
    return syn_ok, lines


def selftest():
    """[2026-07-23] OFFLINE validation — no ledger fetch — so the WIDEN
    direction is under continuous test (registered in tests/test_selftests.py),
    not only in the network-requiring main(). Exercises reduce (A-F/G) AND
    expand (H/I), then pins the expand-accounting sign in score(): the H
    universe's winners, expanded 1.5x, must register as GAINED>0 and NEVER as
    a reduce 'saved'/'throttled'."""
    T0 = 1_700_000_000            # fixed epoch: deterministic, no wall clock
    ok, lines = run_synthetic_suite(T0)
    print("brain_replay synthetic discrimination suite (offline):")
    for ln in lines:
        print(ln)
    assert ok, "synthetic discrimination suite FAILED (see above)"
    hu = next((tr for tr, ch in synthetic_scenarios_isolated(T0)
               if any(c[1] == "syn-strong" for c in ch)), None)
    assert hu is not None, "H (expand) universe missing"
    tl, _ = simulate(hu, "v3", half_life=14.0)
    sc = score(hu, tl)
    assert sc["expanded"] > 0 and sc["gained"] > 0, \
        f"expand accounting wrong (expected expanded>0, gained>0): {sc}"
    assert sc["throttled"] == 0 and sc["saved"] == 0.0, \
        f"a winning bucket must NEVER throttle: {sc}"
    print(f"expand accounting OK: expanded={sc['expanded']} "
          f"gained=${sc['gained']:+.2f} throttled={sc['throttled']}")
    print("brain_replay --selftest OK")
    return 0


def main():
    trades = era_filter(load_trades())
    print(f"replay universe: {len(trades)} closed era trades, "
          f"{len({t.get('bot') for t in trades})} bots")
    results = {}
    for engine in ("v2", "v3"):
        tl, n_runs = simulate(trades, engine, half_life=14.0)
        results[engine] = score(trades, tl)
        results[engine]["runs"] = n_runs
        results[engine]["timeline"] = tl
    print(f"\n{'ENGINE':8}{'throttled':>10}{'saved$':>9}{'half1':>8}"
          f"{'half2':>8}{'forgone$':>10}{'buckets':>9}")
    for e, r in results.items():
        print(f"{e:8}{r['throttled']:>10}{r['saved']:>+9.2f}{r['h1']:>+8.2f}"
              f"{r['h2']:>+8.2f}{r['forgone']:>+10.2f}{len(r['buckets']):>9}")
    print("\nper-(bot,tag):")
    keys = sorted(set(results["v2"]["buckets"]) | set(results["v3"]["buckets"]))
    for k in keys:
        a = results["v2"]["buckets"].get(k, {"trades": 0, "saved": 0.0})
        b = results["v3"]["buckets"].get(k, {"trades": 0, "saved": 0.0})
        print(f"  {k:48} v2 {a['trades']:>3}t ${a['saved']:>+7.2f}   "
              f"v3 {b['trades']:>3}t ${b['saved']:>+7.2f}")
    print("\nhalf-life sweep (v3):")
    for hl in (7.0, 14.0, 28.0):
        tl, _ = simulate(trades, "v3", half_life=hl)
        r = score(trades, tl)
        print(f"  HL={hl:>4.0f}d  saved ${r['saved']:>+7.2f}  "
              f"h1 ${r['h1']:>+6.2f} h2 ${r['h2']:>+6.2f}  "
              f"forgone ${r['forgone']:>+6.2f}")
    v2, v3 = results["v2"], results["v3"]
    ok_total = v3["saved"] >= v2["saved"] - 1.0
    ok_halves = v3["h1"] >= v2["h1"] - 1.0 and v3["h2"] >= v2["h2"] - 1.0
    ok_forgone = v3["forgone"] >= v2["forgone"] - 1.0

    # ---- synthetic discrimination suite ------------------------------------
    t0 = min(t["_close_epoch"] for t in trades)
    syn_ok, syn_lines = run_synthetic_suite(t0)
    print("\nsynthetic discrimination suite:")
    for ln in syn_lines:
        print(ln)

    verdict = "PASS" if (ok_total and ok_halves and ok_forgone and syn_ok) else "FAIL"
    print(f"\nVERDICT: {verdict}  (ledger total {'ok' if ok_total else 'WORSE'}, "
          f"halves {'ok' if ok_halves else 'WORSE'}, "
          f"false-throttle {'ok' if ok_forgone else 'WORSE'}, "
          f"synthetic {'ok' if syn_ok else 'FAIL'})")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    sys.exit(main())
