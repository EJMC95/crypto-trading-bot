#!/usr/bin/env python3
"""🎫 THE TICKET TAKER vs A COIN FLIP — the (hm) random-entry null.

**Eamon, 2026-09-10:** *"sounds good"* — run the null before tomorrow's
go-live decision on the two READY books.

WHY THIS IS THE ONE TEST THAT MATTERS HERE. The taker reads **READY, 6 of 6
bars**. But (hm) measured that on this venue **a random entry earns +0.2% to
+1.1%/trade for free**, because the whole 438d tape is one falling-BTC regime
— so "mean > 0" and "both halves positive" are satisfied by the DRIFT, not by
the edge, and a directional book is graded against RANDOM, never against zero.
(hm) measured exactly that on THIS book and random BEAT it: six runs,
P(coin flip >= taker) 0.55-0.84. The book's own mean today (+0.953%/trade)
sits INSIDE the band a coin flip pays.

**AND THE SPLIT IS THE POINT.** The graded era is 5 lenses x BOTH sides, but
`lighter_ticket_taker.LIVE_SIDES` is `{"divergence": {"short"}}` — one lens,
one side. Measured on the era ledger: **160 of 206 closes are
`long-breakoutup` and only 46 are `short-divergence`**, so **78% of the READY
verdict comes from a family the live arm cannot fill.** A pooled null would
answer a question nobody is deciding. This reports POOLED and PER-FAMILY, and
the live-relevant number is the `short-divergence` one.

HOW THE COUNTERFACTUAL IS BUILT, and every piece is the taker's OWN:
  * entries: for each era close, K random entry hours on the SAME COIN inside
    the era window — the (hm) construction ("random entries on the LENS'S OWN
    COINS, same window, same bracket");
  * exits: `lighter_ticket_taker.exit_reason`, IMPORTED. The routing comes
    from the module's own `bull_exit(lens)` — breakout/breakoutup get the
    TREND exit (no TP cap, wide BRK_SL, BRK_TRAIL off the peak), divergence
    keeps its fixed bracket — and the max-hold is GRAFTED from the close's
    own `extra.bars` stamp, exactly as the live loop does at its call site;
  * `peak_ret` is tracked bar by bar, because the caller owns it and a trend
    exit without it silently becomes a fixed bracket.

**BLOCKER (1) FROM THE CARRIED ROW IS CLOSED BY CONSTRUCTION.** The prior
design did `os.environ.setdefault("TT_BULL_MODE", "on")` at import and raced
`import lighter_ticket_taker` — mutating process-global env and reddening
three unrelated selftests. This mutates NOTHING. It asks `bull_exit` what the
routing is, and when the answer is `(None, None)` — i.e. this process has
BULL_MODE off while the graded era ran `bull: True` — it **REFUSES** (exit 2)
and tells you to re-run with `TT_BULL_MODE=on` in the COMMAND, not the import.
Fail-closed beats a silent grade of the wrong bracket.

CALIBRATION GATE, and it REFUSES rather than reports (the (gx) rule). The
harness first replays the taker's OWN entries through the same walk and
compares the result to the ledger's realised mean. Beyond tolerance, nothing
is printed: a harness that cannot reproduce what DID happen may not say what
WOULD have.

DECLARED DIVERGENCE, because it bounds what this can claim: the walk steps
**1h candle closes** while the live loop decides every ~5 min, so exits land
LATER here than in the book. This is why the calibration gate exists — and
note the convention is IDENTICAL on both sides of the comparison, so it
cancels in the contrast even where it shifts the level.

Exit: 0 verdict printed · 2 refused (calibration, dark tape, or BULL_MODE).
"""
import argparse
import collections
import datetime as _dt
import json
import math
import os
import random
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bot_pnl_store as store              # noqa: E402
import golive_readiness as gr              # noqa: E402
import lighter_ticket_taker as tt          # noqa: E402

BASE = "https://pnl-dashboard-production-858c.up.railway.app"
API = "https://mainnet.zklighter.elliot.ai"
BOT = "lighter-ticket-taker-lshadow"
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     ".taker_null_tape")

#: The era boundary the GRADER publishes for this book — imported as a fact,
#: never re-derived. (hc): a trade's policy is fixed when it is TAKEN.
ERA_SINCE = "2026-07-30T11:09:46+00:00"

#: Percentage points of per-trade mean. A wrong bracket, a missing filter or a
#: fraction-vs-percent slip blows through this; the 1h-vs-5min exit convention
#: should not.
CALIB_TOL_PP = 0.60

#: Draws per real close. 200 x 206 closes = 41,200 counterfactual trades.
DRAWS = 200

#: PRE-DECLARED before any number was seen (I21).
DECISION_RULE = {
    "statistic": "mean %/trade, taker vs the null distribution of the same "
                 "count of random entries on the same coins in the same window",
    "clusters": "UTC day — overlapping holds are not independent draws ((kw))",
    "pass": "P(null >= taker) <= 0.05 on the family being decided",
    "fail": "P(null >= taker) > 0.05 — the book is not distinguishable from a "
            "coin flip on this venue's drift, which is what (hm) already "
            "measured on this exact book",
    "decides": "short-divergence ALONE decides a go-live, because LIVE_SIDES "
               "admits nothing else. The pooled number is context, not the "
               "verdict.",
}


def _ts(v):
    if v is None:
        return None
    try:
        t = _dt.datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=_dt.timezone.utc)


def _get(url, tries=3):
    for a in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=45) as fh:
                return json.load(fh)
        except Exception:                                    # noqa: BLE001
            if a == tries - 1:
                return None
            time.sleep(2 * (a + 1))
    return None


def load_era():
    """The era closes, quarantine- and phantom-filtered, keyed on the OPEN."""
    raw = _get(BASE + "/trades.json?limit=5000&source=paper")
    if raw is None:
        return []
    rows = raw if isinstance(raw, list) else raw.get("trades",
                                                     raw.get("data", []))
    era = _ts(ERA_SINCE)
    out = []
    for r in rows:
        if not isinstance(r, dict) or r.get("bot") != BOT:
            continue
        if r.get("side") == "skip":
            continue
        if store.is_quarantined(r.get("bot"), r.get("pair"),
                                r.get("closed_at")):
            continue
        if gr.is_phantom_close(r):
            continue
        o = _ts(r.get("opened_at"))
        if not o or o < era:
            continue
        out.append(r)
    out.sort(key=lambda r: _ts(r["opened_at"]))
    return out


def lens_of(r):
    """`long-breakoutup_trail` -> 'breakoutup'. The tag is the record."""
    tag = str(r.get("tag") or r.get("reason") or "")
    head = tag.split("_")[0]
    return head.split("-", 1)[1] if "-" in head else head


def family_of(r):
    tag = str(r.get("tag") or r.get("reason") or "")
    return tag.split("_")[0]        # 'long-breakoutup' / 'short-divergence'


def side_is_long(r):
    """Is this close a LONG? **THE TAG IS THE RECORD** — `lens_of`'s own rule,
    one field over.

    [2026-09-11 (aar)] CORRECTED. Both call sites read
    `str(r.get("side")) == "long"`, and the public `/trades.json` feed carries
    `side: null` on a large minority of rows — so `str(None) == "long"` is
    False and the row was replayed as a SHORT. Measured on the graded era:
    155 rows side=long/reason=long, 34 side=short/reason=short, 12
    side=None/reason=short (right by accident), and **7 side=None with a LONG
    reason — sign-flipped**, every one `long-breakoutup`.

    The error was silent because it cancels in aggregate: the calibration gate
    still read 0.009pp, and a flipped row is wrong by up to 38pp on its own.
    It sits in `draw_null` too, so it mis-signed the NULL as well as the
    replay.

    Derived from the reason/tag prefix, which every row carries, with the
    `side` column only as a fallback for a row whose tag is unreadable."""
    tag = str(r.get("tag") or r.get("reason") or "")
    head = tag.split("_")[0]
    if head.startswith("long"):
        return True
    if head.startswith("short"):
        return False
    return str(r.get("side")) == "long"


def routing(lens, stamped):
    """The taker's OWN exit routing for `lens`, with the stamped max-hold
    grafted on exactly as the live call site does.

    -> (bars, trail) or None when this process cannot reproduce the era's
    routing, which the caller turns into a REFUSAL. No env is read or written
    here: `bull_exit` is asked, never re-implemented ((hj): a second copy of a
    rule is a second rule)."""
    ebars, etrail = tt.bull_exit(lens)
    if ebars is None and etrail is None:
        return None                      # BULL_MODE off -> cannot reproduce
    if ebars:
        ebars = (ebars[0], ebars[1], stamped[2])
    # The `else 0.0` mirrors the live call site's own inertness guard ((dg):
    # "pass trail=0.0 (NOT None) so exit_reason cannot fall back to the global
    # TT_TRAIL_PCT"). DECLARED EQUIVALENT MUTANT: `bull_exit` never returns a
    # non-None `ebars` beside a None trail, so this branch is unreachable and
    # no test can redden it — a mutation of the fallback value survives by
    # construction. Kept because deleting a guard the bot itself carries would
    # make this walk diverge from the loop it is supposed to reproduce.
    return (ebars or stamped), (etrail if etrail is not None else 0.0)


def walk(entry_px, t_open, is_long, bars, trail, series):
    """Run the taker's REAL `exit_reason` forward over 1h closes from
    `t_open`, tracking `peak_ret` as the live caller does.

    -> (return_fraction, reason) or None when the tape cannot cover it."""
    if not entry_px or entry_px <= 0 or not series:
        return None
    peak = 0.0
    last = None
    # `exit_reason` takes DATETIMES for opened/t_now — it calls
    # `(t_now - opened).total_seconds()` on them. Passing epochs raises, which
    # the selftest caught on its first run; the risk of "fixing" it by coercing
    # inside exit_reason would have been a second copy of the module's clock.
    _open_dt = _dt.datetime.fromtimestamp(t_open, _dt.timezone.utc)
    for t, close in series:
        if t <= t_open:
            continue
        ret = (close / entry_px - 1.0) * (1.0 if is_long else -1.0)
        peak = max(peak, ret)
        why = tt.exit_reason(entry_px, close, _open_dt,
                             _dt.datetime.fromtimestamp(t, _dt.timezone.utc),
                             is_long, bars=bars, peak_ret=peak, trail=trail)
        last = (ret, why)
        if why:
            return ret, why
    # tape ran out with the position open: value it where the tape ends, and
    # label it so the caller can see it was NOT a rule exit
    return (last[0], "tape_end") if last else None


def fetch_tape(coins, t0, t1, cache=True):
    """1h closes per coin over [t0, t1]. Cached to disk — the venue throttles
    at ~21 requests/min and this is 49 coins x ~2 pages."""
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, f"h1_{int(t0)}_{int(t1)}.json")
    if cache and os.path.exists(path):
        with open(path) as fh:
            return {k: [(int(a), float(b)) for a, b in v]
                    for k, v in json.load(fh).items()}
    d = _get(API + "/api/v1/orderBookDetails")
    ids = {b["symbol"]: int(b["market_id"])
           for b in ((d or {}).get("order_book_details") or [])}
    out = {}
    for sym in sorted(coins):
        mid = ids.get(sym)
        if mid is None:
            continue
        rows, end = {}, int(t1)
        for _ in range(8):
            url = (f"{API}/api/v1/candles?market_id={mid}&resolution=1h"
                   f"&start_timestamp={end - 500 * 3600}"
                   f"&end_timestamp={end}&count_back=500")
            dd = _get(url)
            page = (dd or {}).get("c") or []
            if not page:
                break
            for c in page:
                t = int(c["t"]) // 1000
                if t0 <= t <= t1:
                    rows[t] = float(c["c"])
            oldest = min(int(c["t"]) // 1000 for c in page)
            if oldest <= t0 or len(page) < 400:
                break
            end = oldest - 1
            time.sleep(0.3)
        if rows:
            out[sym] = [(t, rows[t]) for t in sorted(rows)]
        time.sleep(0.3)
    if cache:
        with open(path, "w") as fh:
            json.dump(out, fh)
    return out


def stats(xs):
    n = len(xs)
    if n == 0:
        return {"n": 0, "mean": 0.0, "se": 0.0, "t": 0.0}
    m = sum(xs) / n
    if n < 2:
        return {"n": n, "mean": m, "se": 0.0, "t": 0.0}
    var = sum((x - m) ** 2 for x in xs) / (n - 1)
    se = math.sqrt(var / n)
    return {"n": n, "mean": m, "se": se, "t": (m / se if se else 0.0)}


def cluster_days(rows, vals):
    """Mean per UTC day, so overlapping holds are not counted as independent
    draws ((kw)/(ky))."""
    by = collections.defaultdict(list)
    for r, v in zip(rows, vals):
        by[_ts(r["opened_at"]).date()].append(v)
    return [sum(v) / len(v) for v in by.values()]


def replay_real(rows, tape):
    """The taker's OWN entries through the same walk — the calibration arm."""
    out, used = [], []
    for r in rows:
        s = tape.get(str(r.get("pair") or "").split("/")[0])
        if not s:
            continue
        stamped = tt.pos_bars({"bars": (r.get("extra") or {}).get("bars")})
        rt = routing(lens_of(r), stamped)
        if rt is None:
            return None, None
        bars, trail = rt
        w = walk(float(r.get("entry_price") or 0),
                 _ts(r["opened_at"]).timestamp(),
                 side_is_long(r), bars, trail, s)
        if w:
            out.append(w[0] * 100.0)
            used.append(r)
    return out, used


def draw_null(rows, tape, k=DRAWS, seed=20260910):
    """K matched-random entries per real close: same coin, same window, same
    bracket, the taker's own exit."""
    rng = random.Random(seed)
    per_close = []
    for r in rows:
        sym = str(r.get("pair") or "").split("/")[0]
        s = tape.get(sym)
        if not s or len(s) < 30:
            continue
        stamped = tt.pos_bars({"bars": (r.get("extra") or {}).get("bars")})
        rt = routing(lens_of(r), stamped)
        if rt is None:
            return None
        bars, trail = rt
        is_long = side_is_long(r)
        got = []
        for _ in range(k):
            i = rng.randrange(0, len(s) - 2)
            t_open, px = s[i]
            w = walk(px, t_open, is_long, bars, trail, s[i + 1:])
            if w:
                got.append(w[0] * 100.0)
        if got:
            per_close.append((r, got))
    return per_close


def report(argv_k=DRAWS, no_cache=False):
    print("🎫 THE TICKET TAKER vs A COIN FLIP — the (hm) random-entry null\n")
    print("DECISION RULE, pre-declared:")
    for kk in ("statistic", "clusters", "pass", "fail", "decides"):
        print(f"  {kk:<10} {DECISION_RULE[kk]}")
    print()

    rows = load_era()
    if len(rows) < 30:
        print(f"REFUSED — only {len(rows)} era closes read (dark feed?).")
        return 2
    fam = collections.Counter(family_of(r) for r in rows)
    print(f"era since {ERA_SINCE}  n={len(rows)}   families: {dict(fam)}")
    print(f"LIVE_SIDES = {dict((k, sorted(v)) for k, v in tt.LIVE_SIDES.items())}"
          "  <- what the live arm may actually fill\n")

    if routing("breakoutup", (0.04, -0.03, 48.0)) is None:
        print("REFUSED — BULL_MODE is OFF in this process while the graded era "
              "ran bull=True, so `bull_exit` cannot reproduce the era's exit "
              "routing. Re-run with TT_BULL_MODE=on in the COMMAND (this "
              "module mutates no environment — that was blocker (1)).")
        return 2

    coins = {str(r.get("pair") or "").split("/")[0] for r in rows}
    t0 = int(min(_ts(r["opened_at"]) for r in rows).timestamp()) - 3 * 86400
    t1 = int(time.time())
    print(f"fetching 1h tape: {len(coins)} coins, "
          f"{(t1 - t0) / 86400:.0f}d ... (cached at {CACHE})")
    tape = fetch_tape(coins, t0, t1, cache=not no_cache)
    print(f"  tape covers {len(tape)} of {len(coins)} coins\n")
    if len(tape) < 0.6 * len(coins):
        print("REFUSED — tape covers under 60% of the traded coins; a null on "
              "a biased subset is not a null.")
        return 2

    real, used = replay_real(rows, tape)
    if not real:
        print("REFUSED — the calibration replay produced nothing.")
        return 2
    ledger = [float(r["pnl_pct"]) * 100.0 for r in used
              if r.get("pnl_pct") is not None]
    rs, ls = stats(real), stats(ledger)
    drift = abs(rs["mean"] - ls["mean"])
    print(f"calibration  replayed {rs['mean']:+.3f}%/trade vs ledger "
          f"{ls['mean']:+.3f}% on the SAME {len(real)} closes "
          f"(|drift| {drift:.3f}pp, tol {CALIB_TOL_PP:.2f}pp)")
    if drift > CALIB_TOL_PP:
        print("\nREFUSED — a harness that cannot reproduce what DID happen may "
              "not say what WOULD have. No verdict printed.")
        return 2
    print("calibration OK\n")

    per = draw_null(rows, tape, k=argv_k)
    if not per:
        print("REFUSED — no null draws produced.")
        return 2

    print(f"{'family':<20} {'n':>4} {'taker':>9} {'null mean':>10} "
          f"{'excess':>9} {'P(null>=taker)':>15} {'clustered':>10}")
    verdicts = {}
    for label in ("POOLED", "short-divergence", "long-breakoutup"):
        sub = [(r, g) for r, g in per
               if label == "POOLED" or family_of(r) == label]
        if len(sub) < 10:
            print(f"{label:<20} {len(sub):>4}  too thin to decide")
            continue
        srows = [r for r, _ in sub]
        tak = [float(r["pnl_pct"]) * 100.0 for r in srows
               if r.get("pnl_pct") is not None]
        tstat = stats(tak)
        # one null "run" = one draw index across every close, so a run is a
        # whole alternative book, not a single alternative trade
        runs = []
        kk = min(len(g) for _, g in sub)
        for j in range(kk):
            runs.append(sum(g[j] for _, g in sub) / len(sub))
        runs.sort()
        nmean = sum(runs) / len(runs)
        p = sum(1 for x in runs if x >= tstat["mean"]) / len(runs)
        ct = stats(cluster_days(srows, tak))
        print(f"{label:<20} {tstat['n']:>4} {tstat['mean']:>+8.3f}% "
              f"{nmean:>+9.3f}% {tstat['mean'] - nmean:>+8.3f}pp "
              f"{p:>15.3f} {ct['t']:>+9.2f}")
        verdicts[label] = (p, tstat["mean"], nmean)

    print()
    live = verdicts.get("short-divergence")
    if live:
        p, m, nm = live
        ok = p <= 0.05
        print(f"VERDICT on the family a go-live would actually trade "
              f"(short-divergence): P(null >= taker) = {p:.3f} -> "
              f"{'CLEARS' if ok else 'DOES NOT CLEAR'} the pre-declared 0.05 "
              f"bar.")
        print(f"   taker {m:+.3f}%/trade vs a coin flip's {nm:+.3f}%/trade "
              f"on the same coins, same windows, same bracket.")
    print("\nREMINDER: the pooled row is CONTEXT. `LIVE_SIDES` admits "
          "divergence-short only, so the pooled 6/6 is 78% earned by a family "
          "the live arm cannot fill.")
    return 0


def selftest():
    """Offline, pure, and FAST — no network, no env mutation. Blocker (2) was
    a registered selftest running 84-107s against a hard 120s cap; everything
    heavy lives in `report()`."""
    # the tag is the record, and both families parse
    assert lens_of({"tag": "long-breakoutup_trail"}) == "breakoutup"
    assert lens_of({"tag": "short-divergence_tp"}) == "divergence"
    assert family_of({"tag": "short-divergence_tp"}) == "short-divergence"
    # a bare reason (no tag column) still parses — the ledger has both
    assert lens_of({"reason": "long-breakoutup_hold"}) == "breakoutup"

    # the walk uses the taker's REAL exit and honours a stop
    ser = [(i * 3600, 100.0 - i) for i in range(1, 40)]      # falling tape
    r = walk(100.0, 0, True, (0.04, -0.03, 48.0), 0.0, ser)
    assert r and r[1] == "sl" and r[0] < -0.02, r

    # ...and a take-profit on a rising tape
    ser_up = [(i * 3600, 100.0 + i) for i in range(1, 40)]
    r = walk(100.0, 0, True, (0.04, -0.03, 48.0), 0.0, ser_up)
    assert r and r[1] == "tp", r

    # a SHORT is the mirror: the falling tape is a WIN, not a stop
    r = walk(100.0, 0, False, (0.04, -0.03, 48.0), 0.0, ser)
    assert r and r[1] == "tp" and r[0] > 0, r

    # tape that ends with the position open is LABELLED, never silently
    # counted as a rule exit
    r = walk(100.0, 0, True, (9.99, -9.99, 999.0), 0.0, ser_up[:3])
    assert r and r[1] == "tape_end", r

    # peak_ret is tracked: a trail exit needs it, and without it the trend
    # bracket silently degrades to a fixed one
    up_then_down = [(i * 3600, 100.0 + min(i, 10) - max(0, i - 10))
                    for i in range(1, 30)]
    r = walk(100.0, 0, True, (999.0, -0.30, 48.0), 0.06, up_then_down)
    assert r and r[1] == "trail", r

    # routing GRAFTS the stamped hold onto the trend bars and never invents one.
    #
    # [MUTATION M2 SURVIVED THE FIRST ROUND] this block used to sit behind
    # `if rt is not None:` — "only when BULL_MODE is on" — and BULL_MODE is OFF
    # in a bare test process, so the whole thing SKIPPED and the graft
    # assertion never ran. A mutation replacing the stamped hold with 999.0
    # stayed GREEN. That is the (po) inspects-nothing rule inside the guard
    # written to prevent it. Drive the module attribute directly and restore —
    # a LOCAL attribute, never `os.environ` at import, which was blocker (1).
    _saved = tt.BULL_MODE
    try:
        tt.BULL_MODE = True
        rt = routing("divergence", (0.04, -0.03, 12.0))
        assert rt is not None, "BULL_MODE forced on must produce a routing"
        assert rt[0] == (0.04, -0.03, 12.0) and rt[1] == 0.0, rt
        bt = routing("breakoutup", (0.04, -0.03, 12.0))
        assert bt[0][2] == 12.0, ("the stamped max-hold must survive the "
                                  "trend graft", bt)
        assert bt[0][0] == 999.0, ("the trend exit caps no TP", bt)
        assert bt[1] == tt.BRK_TRAIL, bt
        # and the REFUSAL path is real: BULL_MODE off -> None -> the caller
        # refuses rather than grading the wrong bracket
        tt.BULL_MODE = False
        assert routing("breakoutup", (0.04, -0.03, 12.0)) is None
    finally:
        tt.BULL_MODE = _saved

    # clustering collapses a day of overlapping closes into ONE observation
    day = _dt.datetime(2026, 8, 1, tzinfo=_dt.timezone.utc)
    rows = [{"opened_at": (day + _dt.timedelta(hours=h)).isoformat()}
            for h in (1, 2, 3)]
    assert cluster_days(rows, [1.0, 2.0, 3.0]) == [2.0]

    # [(aar)] THE SIDE BUG. `side: null` on the public feed made
    # `str(None) == "long"` False, so 7 of 208 era closes — every one
    # `long-breakoutup` — were replayed and NULLED as shorts. The tag is the
    # record. Mutation: revert either call site to `str(r.get("side"))` => red.
    assert side_is_long({"side": None, "reason": "long-breakoutup_trail"})
    assert side_is_long({"side": None, "tag": "long-breakoutup"})
    assert not side_is_long({"side": None, "reason": "short-divergence_tp"})
    assert side_is_long({"side": "long", "reason": ""}), "fallback to the column"
    assert not side_is_long({"side": None, "reason": ""}), "no tag, no side"
    import ast as _ast
    _src = open(__file__).read()
    for _fn in ("replay_real", "draw_null"):
        _f = next(n for n in _ast.walk(_ast.parse(_src))
                  if isinstance(n, _ast.FunctionDef) and n.name == _fn)
        _u = _ast.unparse(_f)
        assert "side_is_long(" in _u, f"{_fn} must ASK the owner"
        assert "'side') == 'long'" not in _u, \
            f"{_fn} still infers side from the nullable column"
    print("study_taker_random_null selftest OK")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--draws", type=int, default=DRAWS)
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    return report(a.draws, a.no_cache)


if __name__ == "__main__":
    raise SystemExit(main())
