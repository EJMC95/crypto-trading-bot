#!/usr/bin/env python3
"""study_exit_sweep.py — fit each book its own exit, on Lighter's own candles.

WHY (2026-07-30, operator: "lets find the best entry and exits to implement into
the system, individually tailored, a suit fitting each bot").

`(gq)` measured which exit reason each book's money came from. That is
observational: it says what the shipped rule DID. It cannot say what a different
rule WOULD have done. This does — by replaying each book's OWN trades under
alternative exit rules against Lighter's own hourly candles.

THE METHOD, and every constraint it buys:

  ENTRIES ARE HELD CONSTANT. The trades come from the book's real ledger, so the
  entry side is never fitted. Only the exit rule varies. This is the single most
  important property: a joint entry+exit grid search on a few dozen trades would
  find a beautiful rule and mean nothing, and that is precisely the mistake a
  "tailored to perfection" brief invites.

  THROUGHPUT IS MODELLED. The replay is SEQUENTIAL with the book's real position
  cap: a rule that holds winners longer occupies slots, and an entry arriving
  while the book is full is SKIPPED, exactly as the live bot would skip it. This
  is not a detail — 🌾 carry and ⚖️ Counterweight are both at their caps, so a
  naive per-trade sweep would report "hold longer, earn more" while silently
  ignoring the trades that holding longer prevents. Every per-trade exit study
  that omits this is measuring a book with infinite capacity.

  LIGHTER ONLY. Candles come from Lighter's own `/api/v1/candles`. The venue we
  trade is the venue we measure (CLAUDE.md); a rule fitted on another venue's
  path is a hypothesis about Lighter, not a result.

HONEST DIVERGENCES — read these before believing any number:

  * INTRA-HOUR ORDERING IS UNKNOWABLE from hourly OHLC. When a bar's range
    touches both the stop and the target, this harness assumes THE ADVERSE ONE
    FIRST. That is the conservative choice and it biases results DOWN; the
    opposite assumption is how backtests lie.
  * SLIPPAGE ON THE EXIT IS NOT MODELLED. Fills are at the rule's trigger price.
    Lighter is zero-fee (measured: all 203 active books report taker/maker
    0.0000), so fees are genuinely absent rather than ignored — but slippage is
    not, and its omission is OPTIMISTIC. Treat a thin margin as no margin.
  * FUNDING ACCRUAL IS NOT MODELLED. For a directional book that is a small
    drag; for a FUNDING book it is the entire P&L, which is why funding books
    are refused outright (see FUNDING_BOOKS) rather than reported with a caveat.
  * ONE REGIME. Lighter's whole tape is one falling-BTC market (item 18). A
    directional book's fitted exit is fitted to that regime only.

ANTI-OVERFIT FLOORS, borrowed from the scout tuner's own doctrine, because a
grid search over a few dozen trades will always produce a winner:
  * >= MIN_CLOSES trades, or the book is not swept at all.
  * The winner must beat the SHIPPED rule in BOTH HALVES of the window, not
    just overall.
  * The winner must beat it by more than MIN_EDGE_PCT per trade, so noise does
    not get promoted.
  * A winner sitting on a GRID EDGE is reported as unbounded, not as a result —
    the optimum is outside what was searched.

READ-ONLY. It proposes; it enacts nothing, writes no lever, and moves no gate.
Under "never modify bot logic without backtesting first" this IS the backtest —
and its output is a candidate for review, not permission.

Usage:
  python3 scripts/study_exit_sweep.py --book lighter-dislocation-lshadow
  python3 scripts/study_exit_sweep.py --all --json sweep.json
  python3 scripts/study_exit_sweep.py --selftest
"""
import argparse
import json
import os
import statistics as st
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

LIGHTER = os.environ.get("LIGHTER_API", "https://mainnet.zklighter.elliot.ai")
DASH = os.environ.get(
    "DASH_URL", "https://pnl-dashboard-production-858c.up.railway.app")

MIN_CLOSES = int(os.environ.get("SWEEP_MIN_CLOSES", "10"))
MIN_EDGE_PCT = float(os.environ.get("SWEEP_MIN_EDGE_PCT", "0.05"))
MAX_HORIZON_H = int(os.environ.get("SWEEP_MAX_HORIZON_H", "168"))

#: Books whose P&L is funding accrual, not price movement. A price-path sweep
#: measures the WRONG THING for these, so they are refused rather than reported
#: with a footnote nobody reads. Their exit question ("should the flip have
#: waited for the decay?") needs the APR telemetry `(gr)` added, and a funding
#: sweep off `/api/v1/fundings` — a different instrument, not this one.
FUNDING_BOOKS = {
    "perps-funding-carry-lshadow",
    "perps-funding-carry",
    "perps-funding-spread-lshadow",
}


# ---------------------------------------------------------------- venue data
def _get(path, **params):
    url = f"{LIGHTER}{path}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode())


def market_ids():
    """{symbol: market_id} from the venue's own book list. {} on trouble."""
    try:
        rows = _get("/api/v1/orderBookDetails").get("order_book_details") or []
    except Exception as e:      # noqa: BLE001
        print(f"market_ids failed: {type(e).__name__}: {e}", file=sys.stderr)
        return {}
    return {str(r.get("symbol")): r.get("market_id") for r in rows
            if r.get("symbol") is not None and r.get("market_id") is not None}


def fetch_candles(market_id, start_ts, end_ts):
    """Hourly OHLC over [start, end] -> {hour_ts: (o, h, l, c)}.

    Paged backward at the venue's 500-bar cap, the same shape
    `backtest_funding_lighter.fetch_candles` uses (proven against this API).
    """
    out, end = {}, int(end_ts)
    seen_oldest = None
    while end > start_ts:
        try:
            cs = _get("/api/v1/candles", market_id=market_id, resolution="1h",
                      start_timestamp=max(int(start_ts), end - 500 * 3600),
                      end_timestamp=end, count_back=500).get("c") or []
        except Exception:      # noqa: BLE001
            break
        if not cs:
            break
        for c in cs:
            try:
                out[int(c["t"]) // 1000] = (float(c["o"]), float(c["h"]),
                                            float(c["l"]), float(c["c"]))
            except (KeyError, TypeError, ValueError):
                continue
        oldest = min(int(c["t"]) // 1000 for c in cs)
        if oldest <= start_ts or (seen_oldest is not None and oldest >= seen_oldest):
            break
        seen_oldest, end = oldest, oldest - 3600
    return {t: v for t, v in out.items() if start_ts <= t <= end_ts}



# ------------------------------------------------------------ shipped rules
#: Each book's REAL exit rule, read from its own module rather than guessed.
#:
#: [2026-07-30 (gx)] THE SWEEP'S OWN NAMED BLOCKER. (gt) could not calibrate
#: because the shipped rule was passed in by hand: on pm-gillard a guessed
#: {tp 2%, sl 2%, hold 4h} replayed to +0.030%/trade against a book whose real
#: mean is negative, so every candidate was ranked in a world that is not this
#: one and the calibration gate correctly withheld everything. A counterfactual
#: harness is only as good as its baseline, and the baseline was fiction.
#:
#: (attr, transform) per rule key. THREE hazards this table exists to absorb,
#: each of which would silently corrupt a sweep:
#:   * SIGN — the taker stores `TT_SL = -0.03`. `walk_exit` wants a positive
#:     magnitude, so a raw read would place the stop ABOVE a long's entry and
#:     exit instantly at a profit. `abs`.
#:   * UNITS — Snap Back's exit is 40 BPS, the sniper's hold is in SECONDS.
#:     A raw 40 would be read as 4,000%, and 21,600 as 21,600 hours.
#:   * NOT AN ENV VAR AT ALL — the sniper's TP/SL/hold are BARE MODULE
#:     LITERALS (`TAKE_PROFIT_PCT = 0.15`). No env var, no lever, nothing can
#:     reach them; only a code edit can. Read from the module so they are at
#:     least visible, and flagged below so that fact is on the record.
_pct = lambda v: float(v)
_abs = lambda v: abs(float(v))
_bps = lambda v: float(v) / 1e4
_sec_h = lambda v: float(v) / 3600.0

BOOK_EXITS = {
    "lighter-ticket-taker-lshadow": ("lighter_ticket_taker", {
        "tp_pct": ("TAKE_PROFIT", _pct), "sl_pct": ("STOP_LOSS", _abs),
        "max_hold_h": ("MAX_HOLD_H", _pct), "trail_pct": ("TRAIL_PCT", _pct)}),
    "lighter-ticket-taker-lighter": ("lighter_ticket_taker", {
        "tp_pct": ("TAKE_PROFIT", _pct), "sl_pct": ("STOP_LOSS", _abs),
        "max_hold_h": ("MAX_HOLD_H", _pct), "trail_pct": ("TRAIL_PCT", _pct)}),
    "lighter-perp-sniper-lshadow": ("lighter_perp_sniper", {
        "tp_pct": ("TAKE_PROFIT_PCT", _pct), "sl_pct": ("STOP_LOSS_PCT", _abs),
        "max_hold_h": ("MAX_HOLD_SEC", _sec_h)}),
    "lighter-dislocation-lshadow": ("lighter_dislocation_bot", {
        "tp_pct": ("EXIT_BPS", _bps)}),
    "crypto-trend-daily-lshadow": ("lighter_trend_bot", {
        "sl_pct": ("CATASTROPHIC_STOP", _abs)}),
    "equities-regime-lshadow": ("lighter_index_bot", {
        "sl_pct": ("CATASTROPHIC_STOP", _abs)}),
}

#: Books whose exit constants are BARE MODULE LITERALS — no env var, no lever.
#: Recorded because "we could tune this" is false for them today: a code edit
#: and a redeploy is the only path, so they cannot participate in the growth
#: rail at all, however good a value the sweep eventually finds.
HARDCODED_EXITS = {"lighter-perp-sniper-lshadow"}


# [2026-07-30 (gx)] THE PARLIAMENT, read from its own strategy table. These six
# matter disproportionately here: pm-gillard is the ONLY book in the fleet whose
# every close carries a price (238 of 238), so it is the only one the sweep can
# CALIBRATE against today — and its shipped rule was the missing half of that.
# Read via `parliament.strategies.base_params`, the same function the running
# bots call, so env overrides and clamping are applied exactly as in production
# rather than re-derived from the defaults table.
def _parliament_rules():
    try:
        from parliament.strategies import PM_BOTS, base_params
    except Exception:      # noqa: BLE001
        return {}
    out = {}
    for base, (_label, strat) in PM_BOTS.items():
        try:
            p = base_params(strat, base)
        except Exception:      # noqa: BLE001
            continue
        rule = {}
        if p.get("tp_pct"):
            rule["tp_pct"] = float(p["tp_pct"])
        if p.get("sl_pct"):
            rule["sl_pct"] = abs(float(p["sl_pct"]))
        if p.get("max_hold_hr"):
            rule["max_hold_h"] = float(p["max_hold_hr"])
        if rule:
            out[base + "-lshadow"] = rule
    return out


_PM_RULES = _parliament_rules()


def shipped_rule(book):
    """The book's ACTUAL exit rule, read from its module. None if unknown.

    Imports the module rather than parsing env defaults, because some books
    (the sniper) hold their exit constants as bare literals that no
    `os.environ.get` parser can see. A missing attribute yields None for that
    key rather than a guess — a partially-known rule is still a better
    baseline than an invented one, and `calibrate` will say so either way.
    """
    if book in _PM_RULES:
        return dict(_PM_RULES[book])
    spec = BOOK_EXITS.get(book)
    if spec is None:
        return None
    mod_name, fields = spec
    try:
        mod = __import__(mod_name)
    except Exception:      # noqa: BLE001
        return None
    rule = {}
    for key, (attr, xform) in fields.items():
        v = getattr(mod, attr, None)
        if v is None:
            continue
        try:
            rule[key] = xform(v)
        except (TypeError, ValueError):
            continue
    # a zero trail/tp means DISABLED, not "exit at entry" — the taker ships
    # TT_TRAIL_PCT=0 and reading that as a 0% trail would close every position
    # on its first bar.
    return {k: v for k, v in rule.items() if v} or None


# ---------------------------------------------------------------- the replay
def walk_exit(candles, entry_ts, entry_px, is_long, rule, max_horizon_h=None):
    """When does ONE position leave, under `rule`? -> (exit_ts, exit_px, why).

    rule: {"tp_pct", "sl_pct", "max_hold_h", "trail_pct"} — any may be None.
    Returns why in {"tp","sl","trail","max_hold","horizon"}.

    INTRA-BAR ORDERING: if a bar touches both the adverse level and the target,
    the ADVERSE one is taken. Hourly OHLC cannot resolve the true order, and
    assuming the favourable one is the classic way a backtest flatters itself.
    """
    if not candles or not entry_px or entry_px <= 0:
        return None, None, "no-data"
    horizon = MAX_HORIZON_H if max_horizon_h is None else max_horizon_h
    tp, sl = rule.get("tp_pct"), rule.get("sl_pct")
    hold, trail = rule.get("max_hold_h"), rule.get("trail_pct")
    sign = 1.0 if is_long else -1.0

    tp_px = entry_px * (1 + sign * tp) if tp else None
    sl_px = entry_px * (1 - sign * sl) if sl else None

    hours = sorted(t for t in candles if t >= entry_ts - 3600)
    peak = entry_px                      # best price seen, for the trail
    for i, t in enumerate(hours):
        if t > entry_ts + horizon * 3600:
            break
        o, h, l, c = candles[t]
        held_h = max(0.0, (t - entry_ts) / 3600.0)

        # trailing stop rides the favourable extreme
        trail_px = None
        if trail:
            peak = max(peak, h) if is_long else min(peak, l)
            trail_px = peak * (1 - sign * trail)

        adverse = [p for p in (sl_px, trail_px) if p is not None]
        hit_adverse = any((l <= p) if is_long else (h >= p) for p in adverse)
        hit_tp = tp_px is not None and ((h >= tp_px) if is_long else (l <= tp_px))

        if hit_adverse:
            # take the WORST adverse level touched — conservative
            p = min(adverse) if is_long else max(adverse)
            why = "sl" if (sl_px is not None and p == sl_px) else "trail"
            return t, p, why
        if hit_tp:
            return t, tp_px, "tp"
        if hold is not None and held_h >= hold:
            return t, c, "max_hold"
    if hours:
        last = min(hours[-1], entry_ts + horizon * 3600)
        return last, candles[hours[-1]][3], "horizon"
    return None, None, "no-data"


def simulate(trades, candles_by_sym, rule, cap=None, max_horizon_h=None):
    """SEQUENTIAL portfolio replay under one exit rule.

    `trades`: [{sym, entry_ts, entry_px, is_long}] — the book's REAL entries.
    `cap`: max concurrent positions; an entry arriving while full is SKIPPED,
    which is what makes this a portfolio result rather than a per-trade one.
    """
    order = sorted(trades, key=lambda t: t["entry_ts"])
    open_until = []                       # exit_ts of currently-open positions
    closed, skipped = [], 0
    for tr in order:
        open_until = [x for x in open_until if x > tr["entry_ts"]]
        if cap is not None and len(open_until) >= cap:
            skipped += 1
            continue
        cs = candles_by_sym.get(tr["sym"]) or {}
        xt, xp, why = walk_exit(cs, tr["entry_ts"], tr["entry_px"],
                                tr["is_long"], rule, max_horizon_h)
        if xt is None or not xp:
            continue
        sign = 1.0 if tr["is_long"] else -1.0
        ret = sign * (xp - tr["entry_px"]) / tr["entry_px"]
        closed.append({"sym": tr["sym"], "entry_ts": tr["entry_ts"],
                       "exit_ts": xt, "ret": ret, "why": why,
                       "held_h": (xt - tr["entry_ts"]) / 3600.0})
        open_until.append(xt)
    return {"closed": closed, "skipped": skipped}


def score(sim):
    """Portfolio stats for one rule. `halves` is the both-halves test the
    tuner's floors require — computed on the CLOSE order, matching how the
    go-live gate splits a window."""
    cl = sim["closed"]
    n = len(cl)
    if not n:
        return {"n": 0, "mean_pct": None, "total_pct": None, "h1": None,
                "h2": None, "median_hold_h": None, "skipped": sim["skipped"],
                "why": {}}
    seq = sorted(cl, key=lambda c: c["exit_ts"])
    rets = [c["ret"] for c in seq]
    half = n // 2
    why = {}
    for c in cl:
        why[c["why"]] = why.get(c["why"], 0) + 1

    # [2026-07-30] MAX DRAWDOWN and PEAK CONCURRENCY, added immediately after
    # the harness's FIRST real run produced a textbook trap: on pm-gillard's 238
    # priced closes every top rule had NO STOP and a long hold, claiming
    # +2.105%/trade against the book's real -1.4%. Removing a stop always
    # flatters an in-sample choppy tape — losers recover, until one does not —
    # and without these two columns nothing in the output argued back.
    #   * max_dd_pct penalises the risk a no-stop rule actually takes, and the
    #     go-live gate has a 15% drawdown bar that such a rule would breach.
    #   * peak_open is the exposure a rule DEMANDS. A rule needing 40
    #     simultaneous positions is not a rule this book can run, whatever its
    #     mean says — and with cap=None the simulator will happily report it.
    eq, peak, dd = 0.0, 0.0, 0.0
    for r in rets:
        eq += r
        peak = max(peak, eq)
        dd = min(dd, eq - peak)
    events = sorted([(c["entry_ts"], 1) for c in cl]
                    + [(c["exit_ts"], -1) for c in cl])
    cur = peak_open = 0
    for _t, d in events:
        cur += d
        peak_open = max(peak_open, cur)

    return {
        "n": n,
        "mean_pct": round(100 * st.mean(rets), 4),
        "total_pct": round(100 * sum(rets), 3),
        "h1": round(100 * sum(rets[:half]), 3) if half else 0.0,
        "h2": round(100 * sum(rets[half:]), 3),
        "median_hold_h": round(st.median(c["held_h"] for c in cl), 2),
        "win_pct": round(100 * sum(1 for r in rets if r > 0) / n, 1),
        "max_dd_pct": round(100 * abs(dd), 3),
        "peak_open": peak_open,
        "skipped": sim["skipped"],
        "why": why,
    }


def on_grid_edge(rule, grid):
    """Is this rule's winning value at the boundary of what was searched? A
    winner on the edge means the optimum is OUTSIDE the grid, so the result is
    'unbounded in this direction', never 'the best exit is X'."""
    edges = []
    for k, vals in grid.items():
        v = rule.get(k)
        opts = [x for x in vals if x is not None]
        if v is None or not opts:
            continue
        if v == min(opts) or v == max(opts):
            edges.append(k)
    return edges


def sweep(trades, candles_by_sym, grid, cap=None, shipped=None,
          min_closes=None, min_edge=None, max_horizon_h=None,
          actual_mean_pct=None):
    """Every combination in `grid`, plus the verdict against `shipped`."""
    min_closes = MIN_CLOSES if min_closes is None else min_closes
    min_edge = MIN_EDGE_PCT if min_edge is None else min_edge
    if len(trades) < min_closes:
        return {"refused": f"{len(trades)} trades < {min_closes} floor",
                "results": []}

    keys = sorted(grid)
    combos = [{}]
    for k in keys:
        combos = [dict(c, **{k: v}) for c in combos for v in grid[k]]

    results = []
    for rule in combos:
        s = score(simulate(trades, candles_by_sym, rule, cap, max_horizon_h))
        if s["n"]:
            results.append({"rule": rule, **s})
    results.sort(key=lambda r: -(r["total_pct"] or 0))

    out = {"results": results, "n_rules": len(combos), "cap": cap}
    if shipped is not None:
        base = score(simulate(trades, candles_by_sym, shipped, cap, max_horizon_h))
        out["shipped"] = {"rule": shipped, **base}
        # CALIBRATE FIRST. A harness that does not reproduce the observed result
        # may not recommend an alternative to it.
        ok, detail = calibrate(base, actual_mean_pct)
        out["calibration"] = {"ok": ok, "detail": detail}
        if not ok:
            out["verdict"] = {"keep_shipped": True, "uncalibrated": True,
                              "why": "calibration failed: " + detail}
            return out
        winner = next((r for r in results
                       if _clears(r, base, min_edge, cap)), None)
        out["verdict"] = _verdict(winner, base, grid, min_edge)
    return out


#: How far the replayed SHIPPED rule may sit from the book's ACTUAL ledger mean
#: before the sweep refuses to recommend anything (percentage points per trade).
CALIB_TOL_PP = float(os.environ.get("SWEEP_CALIB_TOL_PP", "0.25"))


def calibrate(replayed_shipped, actual_mean_pct, tol_pp=None):
    """Does the harness REPRODUCE the book it is counterfactualising?

    THE GATE THAT MAKES THIS INSTRUMENT TRUSTWORTHY, added the moment its first
    real run exposed the need. On pm-gillard the replayed shipped rule scored
    mean **+0.030%** while the book's actual ledger mean is NEGATIVE. A harness
    that cannot reproduce what did happen has no standing to tell you what would
    have happened — every candidate it ranks is ranked in a world that is not
    this one.

    Divergence has three known sources, all of them real here:
      * the shipped rule passed in is a GUESS unless it was read from the bot,
      * funding accrual is not modelled,
      * exit slippage is not modelled.

    So a failed calibration is not necessarily a bug — it is a statement that
    the missing pieces are large enough to matter for this book. Either way the
    verdict must be withheld. Returns (ok, detail).
    """
    tol = CALIB_TOL_PP if tol_pp is None else tol_pp
    if actual_mean_pct is None or replayed_shipped.get("mean_pct") is None:
        return False, "no baseline to calibrate against"
    gap = replayed_shipped["mean_pct"] - actual_mean_pct
    ok = abs(gap) <= tol
    return ok, (f"replayed {replayed_shipped['mean_pct']:+.3f}%/trade vs actual "
                f"{actual_mean_pct:+.3f}%/trade (gap {gap:+.3f}pp, tol {tol}pp)"
                + ("" if ok else " — RECOMMENDATIONS WITHHELD: unmodelled "
                             "funding/slippage or a wrong shipped rule"))


def _clears(cand, base, min_edge, cap=None):
    """Every floor, together. Deliberately strict: this is the gate that stops
    a grid-search artefact from being presented as a tailored exit."""
    if not cand["n"] or base.get("mean_pct") is None:
        return False
    if cand["mean_pct"] - base["mean_pct"] < min_edge:
        return False
    if (cand["h1"] or 0) <= (base["h1"] or 0):
        return False
    if (cand["h2"] or 0) <= (base["h2"] or 0):
        return False
    # [2026-07-30] A CANDIDATE MAY NOT WIN BY TAKING MORE RISK. Without this,
    # "delete the stop" wins every sweep on every choppy tape: it converts
    # realised losses into unrealised ones and the mean looks better while the
    # equity path gets worse. Measured on the harness's first run — pm-gillard's
    # top five rules were ALL sl_pct=None. A rule must not deepen the drawdown.
    if (cand.get("max_dd_pct") or 0) > (base.get("max_dd_pct") or 0):
        return False
    # ...nor demand exposure the book cannot carry. THE BOUND IS THE CAP, NOT
    # THE BASELINE'S ACCIDENT — corrected the first time a refusal was actually
    # inspected instead of trusted. On pm-gillard the shipped rule happened to
    # peak at 5 concurrent positions while the book's cap is 6, so comparing to
    # the baseline refused a candidate for using 6 of 6 available slots: a
    # capacity the book demonstrably has. That is not the floor's purpose. With
    # no cap supplied there is no declared allowance, so fall back to the
    # baseline's peak as the only available bound (conservative).
    limit = cap if cap is not None else (base.get("peak_open") or 0)
    if (cand.get("peak_open") or 0) > limit:
        return False
    return True


def _verdict(winner, base, grid, min_edge):
    if winner is None:
        return {"keep_shipped": True,
                "why": (f"no rule beat the shipped exit by >= {min_edge}pp per "
                        "trade in BOTH halves — the shipped exit is not the "
                        "problem, or the sample cannot tell")}
    edges = on_grid_edge(winner["rule"], grid)
    return {"keep_shipped": False, "candidate": winner["rule"],
            "edge_pp": round(winner["mean_pct"] - base["mean_pct"], 4),
            "grid_edge": edges,
            "why": ("UNBOUNDED: the winner sits on the grid edge for "
                    f"{edges} — widen the grid before believing a value"
                    if edges else
                    "clears both halves and the per-trade floor")}


# ---------------------------------------------------------------- selftest
def _selftest():
    H = 3600
    t0 = 1_700_000_000 - (1_700_000_000 % H)

    def path(prices):
        """One symbol's candles from a close series; o=h=l=c so the bar range
        is unambiguous and the walk is exactly testable."""
        return {t0 + i * H: (p, p, p, p) for i, p in enumerate(prices)}

    # ---- walk_exit: a long that rises through a 5% target -----------------
    up = path([100, 102, 105, 110])
    ts, px, why = walk_exit(up, t0, 100.0, True, {"tp_pct": 0.05})
    assert why == "tp" and px == 105.0, (ts, px, why)

    # ---- a long that falls through a 3% stop ------------------------------
    down = path([100, 99, 96, 90])
    ts, px, why = walk_exit(down, t0, 100.0, True, {"sl_pct": 0.03})
    assert why == "sl" and px == 97.0, (ts, px, why)

    # ---- THE ADVERSE-FIRST RULE, the assumption that keeps this honest ----
    # one bar spans BOTH levels; the stop must win.
    both = {t0: (100, 100, 100, 100), t0 + H: (100, 110, 90, 100)}
    ts, px, why = walk_exit(both, t0, 100.0, True,
                            {"tp_pct": 0.05, "sl_pct": 0.03})
    assert why == "sl", f"a bar touching both must take the STOP, got {why}"

    # ---- SHORTS are mirrored, not reused ---------------------------------
    ts, px, why = walk_exit(path([100, 98, 95]), t0, 100.0, False,
                            {"tp_pct": 0.05})
    assert why == "tp" and px == 95.0, (px, why)
    ts, px, why = walk_exit(path([100, 102, 104]), t0, 100.0, False,
                            {"sl_pct": 0.03})
    assert why == "sl" and px == 103.0, (px, why)

    # ---- max_hold closes at the close, not the trigger price -------------
    flat = path([100] * 10)
    ts, px, why = walk_exit(flat, t0, 100.0, True, {"max_hold_h": 3})
    assert why == "max_hold" and ts == t0 + 3 * H, (ts, why)

    # ---- a trailing stop rides the peak then gives back -------------------
    ts, px, why = walk_exit(path([100, 120, 100]), t0, 100.0, True,
                            {"trail_pct": 0.10})
    assert why == "trail" and px == 108.0, (px, why)     # 120 * 0.9

    # ---- no candles claims nothing ---------------------------------------
    assert walk_exit({}, t0, 100.0, True, {"tp_pct": 0.05})[2] == "no-data"
    assert walk_exit(flat, t0, 0.0, True, {"tp_pct": 0.05})[2] == "no-data"

    # ---- THE CAP: throughput is modelled, which is the whole point --------
    # three overlapping entries, cap of 1, a rule that holds forever ->
    # exactly ONE fills and two are skipped, as the live bot would skip them.
    cs = {"X": path([100] * 40)}
    trades = [{"sym": "X", "entry_ts": t0 + i * H, "entry_px": 100.0,
               "is_long": True} for i in range(3)]
    held = {"max_hold_h": 30}
    one = simulate(trades, cs, held, cap=1)
    assert len(one["closed"]) == 1 and one["skipped"] == 2, one
    # ...and with no cap all three fill: the cap is doing the work, not a bug
    allf = simulate(trades, cs, held, cap=None)
    assert len(allf["closed"]) == 3 and allf["skipped"] == 0, allf

    # ---- a faster exit FREES the slot -> more trades ----------------------
    quick = simulate(trades, cs, {"max_hold_h": 1}, cap=1)
    assert len(quick["closed"]) == 3, (
        "a 1h hold must let all three through a cap of 1 — if this fails the "
        "throughput model is broken and every 'hold longer' result is a lie")

    # ---- score: halves split on CLOSE order ------------------------------
    s = score(simulate(
        [{"sym": "X", "entry_ts": t0, "entry_px": 100.0, "is_long": True}],
        {"X": path([100, 105])}, {"tp_pct": 0.05}))
    assert s["n"] == 1 and s["mean_pct"] == 5.0 and s["win_pct"] == 100.0, s
    assert score({"closed": [], "skipped": 3})["n"] == 0

    # ---- DRAWDOWN and PEAK CONCURRENCY, the two columns that argue back -----
    # a win then a bigger loss: dd is measured from the equity PEAK, not zero.
    dd = score({"closed": [
        {"sym": "X", "entry_ts": t0, "exit_ts": t0 + H, "ret": 0.10,
         "why": "tp", "held_h": 1},
        {"sym": "X", "entry_ts": t0, "exit_ts": t0 + 2 * H, "ret": -0.30,
         "why": "sl", "held_h": 2}], "skipped": 0})
    assert dd["max_dd_pct"] == 30.0, dd          # peak +10 -> -20
    assert dd["peak_open"] == 2, dd              # both open at t0
    # and a rule that never overlaps demands exposure of 1
    solo = score({"closed": [
        {"sym": "X", "entry_ts": t0, "exit_ts": t0 + H, "ret": 0.01,
         "why": "tp", "held_h": 1},
        {"sym": "X", "entry_ts": t0 + 2 * H, "exit_ts": t0 + 3 * H, "ret": 0.01,
         "why": "tp", "held_h": 1}], "skipped": 0})
    assert solo["peak_open"] == 1, solo

    # ---- THE NO-STOP TRAP must be REFUSED, not promoted --------------------
    # A candidate that improves the mean while DEEPENING the drawdown is the
    # "delete the stop" artifact. _clears must reject it on risk alone.
    base_r = {"mean_pct": 0.0, "h1": 0.0, "h2": 0.0, "max_dd_pct": 5.0,
              "peak_open": 3, "n": 20}
    riskier = {"mean_pct": 2.0, "h1": 1.0, "h2": 1.0, "max_dd_pct": 40.0,
               "peak_open": 3, "n": 20}
    assert not _clears(riskier, base_r, 0.05), (
        "a rule that wins by deepening the drawdown MUST be refused — this is "
        "the trap the harness produced on its own first real run")
    greedier = {"mean_pct": 2.0, "h1": 1.0, "h2": 1.0, "max_dd_pct": 4.0,
                "peak_open": 40, "n": 20}
    assert not _clears(greedier, base_r, 0.05), (
        "a rule demanding exposure the book cannot carry MUST be refused")
    # THE CAP IS THE BOUND, not the baseline's accident. A candidate peaking at
    # 6 when the baseline peaked at 3 but the CAP is 6 is using capacity the
    # book has, and must be allowed. Refusing it was a real over-refusal
    # measured on pm-gillard (shipped peaked at 5, cap 6, candidate 6).
    at_cap = {"mean_pct": 2.0, "h1": 1.0, "h2": 1.0, "max_dd_pct": 4.0,
              "peak_open": 6, "n": 20}
    assert _clears(at_cap, base_r, 0.05, cap=6), (
        "a candidate within the book's declared cap must not be refused for "
        "exceeding the baseline's incidental peak")
    assert not _clears(at_cap, base_r, 0.05, cap=5), "over the cap -> refused"
    assert not _clears(at_cap, base_r, 0.05), (
        "with no cap declared, the baseline's peak is the only bound available")
    honest = {"mean_pct": 2.0, "h1": 1.0, "h2": 1.0, "max_dd_pct": 4.0,
              "peak_open": 3, "n": 20}
    assert _clears(honest, base_r, 0.05), "a genuinely better rule must pass"

    # ---- the floors REFUSE a thin sample --------------------------------
    thin = sweep(trades[:2], cs, {"tp_pct": [0.05]}, min_closes=10)
    assert "refused" in thin, thin

    # ---- GRID EDGE detection: a winner at the boundary is unbounded -------
    g = {"tp_pct": [0.02, 0.04, 0.06]}
    assert on_grid_edge({"tp_pct": 0.06}, g) == ["tp_pct"]
    assert on_grid_edge({"tp_pct": 0.04}, g) == []

    # ---- the VERDICT defaults to keeping the shipped rule ----------------
    # a flat tape: nothing can beat anything, so no candidate may be promoted.
    flat_tr = [{"sym": "X", "entry_ts": t0 + i * H, "entry_px": 100.0,
                "is_long": True} for i in range(12)]
    # A SYNTHETIC world is its own ground truth, so the calibration baseline is
    # the replayed shipped rule itself. Passing it explicitly (rather than
    # letting it default) is deliberate: `calibrate` is FAIL-CLOSED, so omitting
    # the baseline withholds every verdict — which is correct behaviour and would
    # make these assertions pass for the wrong reason.
    flat_cs = {"X": path([100] * 60)}
    flat_base = score(simulate(flat_tr, flat_cs, {"max_hold_h": 4}, None))
    res = sweep(flat_tr, flat_cs, {"max_hold_h": [2, 4, 8]},
                cap=None, shipped={"max_hold_h": 4}, min_closes=10,
                actual_mean_pct=flat_base["mean_pct"])
    assert res["verdict"]["keep_shipped"] is True, res["verdict"]
    # and a REAL improvement is found when one genuinely exists: a rising tape
    # where holding longer earns more, with the shipped rule cutting early.
    #
    # NOTE THE ENTRY SPACING (24h apart, wider than any hold in the grid). The
    # first version of this fixture entered hourly, so the 20h candidate held
    # many positions at once and was REFUSED by the peak_open floor — correctly.
    # The floor was right and the fixture was confounding return with exposure.
    # Spacing them isolates the thing under test: same peak_open (1), better
    # return. A fixture that cannot separate the two cannot test either.
    spaced = [{"sym": "X", "entry_ts": t0 + i * 24 * H, "entry_px": 100.0,
               "is_long": True} for i in range(12)]
    rising = {"X": path([100 + i for i in range(12 * 24 + 40)])}
    rise_base = score(simulate(spaced, rising, {"max_hold_h": 2}, None))
    res2 = sweep(spaced, rising, {"max_hold_h": [2, 20]}, cap=None,
                 shipped={"max_hold_h": 2}, min_closes=10,
                 actual_mean_pct=rise_base["mean_pct"])
    assert res2["verdict"]["keep_shipped"] is False, res2["verdict"]
    assert res2["verdict"]["candidate"]["max_hold_h"] == 20
    assert "UNBOUNDED" in res2["verdict"]["why"], (
        "20 is the grid max here, so the verdict MUST say unbounded rather "
        "than recommend 20 — that caveat is the difference between a study "
        "and a number someone ships")

    # ---- CALIBRATION: no reproduction, no recommendation -----------------
    ok, why = calibrate({"mean_pct": 0.030}, -1.400)
    assert ok is False and "WITHHELD" in why, why
    ok, why = calibrate({"mean_pct": 0.10}, 0.05, tol_pp=0.25)
    assert ok is True and "WITHHELD" not in why, why
    assert calibrate({"mean_pct": None}, 0.05)[0] is False
    assert calibrate({"mean_pct": 0.1}, None)[0] is False

    # an UNCALIBRATED sweep must WITHHOLD even when a candidate would have won.
    # Same rising-tape fixture that legitimately promotes a 20h hold above;
    # here the actual mean is declared wildly different, so nothing ships.
    held_back = sweep(spaced, rising, {"max_hold_h": [2, 20]}, cap=None,
                      shipped={"max_hold_h": 2}, min_closes=10,
                      actual_mean_pct=-99.0)
    assert held_back["verdict"]["keep_shipped"] is True
    assert held_back["verdict"].get("uncalibrated") is True, held_back["verdict"]
    # ...while res2 above, given a truthful baseline, DID recommend — so the
    # gate withholds on divergence and passes through on agreement.
    assert res2["calibration"]["ok"] is True, res2["calibration"]
    assert res2["verdict"].get("uncalibrated") is None

    # ---- funding books are refused, not caveated -------------------------
    assert "perps-funding-carry-lshadow" in FUNDING_BOOKS

    print("study_exit_sweep selftest OK (walk: tp/sl/trail/max_hold/shorts, "
          "adverse-first, cap throughput both ways, floors, grid-edge, verdict "
          "both directions)")


# ---------------------------------------------------------------- main
def _iso(x):
    try:
        return datetime.fromisoformat(str(x).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def load_trades(book, rows):
    """The book's real entries -> the shape simulate() wants. Rows WITHOUT an
    entry price are skipped and counted: before `(gr)` that was every row on
    most books, which is the whole reason this harness could not run."""
    out, no_px = [], 0
    for r in rows:
        if r.get("bot") != book:
            continue
        a = _iso(r.get("opened_at"))
        try:
            px = float(r.get("entry_price"))
        except (TypeError, ValueError):
            px = None
        if a is None or not px:
            no_px += 1
            continue
        sym = str(r.get("pair") or "").split("/")[0].strip()
        out.append({"sym": sym, "entry_ts": int(a.timestamp()), "entry_px": px,
                    "is_long": not str(r.get("side", "")).lower().startswith("s")})
    return out, no_px


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--book", help="dashboard row to sweep")
    ap.add_argument("--all", action="store_true", help="every eligible book")
    ap.add_argument("--cap", type=int, help="max concurrent positions")
    ap.add_argument("--json", help="write results here")
    a = ap.parse_args()
    if a.selftest:
        return _selftest()

    from study_exit_attribution import fetch_trades
    rows = fetch_trades()
    if not rows:
        print("no ledger rows.")
        return

    books = [a.book] if a.book else sorted(
        {r.get("bot") for r in rows if r.get("bot")})
    ids = market_ids()
    out = {}
    for book in books:
        if book in FUNDING_BOOKS:
            print(f"{book}: REFUSED — funding book. Its P&L is accrued funding, "
                  f"not price, so a price-path sweep measures the wrong thing. "
                  f"Needs a funding sweep off /api/v1/fundings.")
            continue
        trades, no_px = load_trades(book, rows)
        if no_px and not trades:
            print(f"{book}: {no_px} closes carry NO entry_price — nothing to "
                  f"sweep. (gr) turned this telemetry on; rows recorded before "
                  f"it cannot be recovered.")
            continue
        if len(trades) < MIN_CLOSES:
            print(f"{book}: only {len(trades)} priced closes "
                  f"(< {MIN_CLOSES}) — refused.")
            continue
        lo = min(t["entry_ts"] for t in trades)
        hi = max(t["entry_ts"] for t in trades) + MAX_HORIZON_H * 3600
        candles = {}
        for sym in sorted({t["sym"] for t in trades}):
            mid = ids.get(sym)
            if mid is None:
                continue
            candles[sym] = fetch_candles(mid, lo, hi)
            time.sleep(0.15)          # the venue's weight budget is shared
        grid = {"tp_pct": [None, 0.02, 0.04, 0.06, 0.10],
                "sl_pct": [None, 0.02, 0.03, 0.05],
                "max_hold_h": [4, 12, 24, 48, 96]}
        res = sweep(trades, candles, grid, cap=a.cap)
        out[book] = res
        print(f"\n{book}: {len(trades)} priced closes, {no_px} unpriced, "
              f"{res.get('n_rules')} rules")
        for r in (res.get("results") or [])[:5]:
            print(f"   {json.dumps(r['rule'])}  n={r['n']:>3d} "
                  f"total={r['total_pct']:>+8.2f}% mean={r['mean_pct']:>+7.3f}% "
                  f"hold={r['median_hold_h']:>6.1f}h skipped={r['skipped']}")
    if a.json and out:
        with open(a.json, "w") as f:
            json.dump(out, f, indent=1)
        print(f"\nwrote {a.json}")
    print("\nREAD-ONLY. A candidate for review, not permission to ship it.")


if __name__ == "__main__":
    main()
