#!/usr/bin/env python3
"""study_taker_hold_floor_2026-09-02.py — the edge audit's hypothesis #2, as a
PRE-REGISTERED instrument: is 🎫 the taker's edge "continuation past a day",
and would a HOLD FLOOR (no price exit before F hours) have earned more on the
entries it actually took?

WHY (EDGE_AUDIT_2026-09-02.md §2/§7). On the taker's own ledger, 1–3d holds
earned +2.219%/trade (t=+3.06, n=57, +$93.8) while 1–4h holds lost −2.595%
(t=−3.19, n=20, −$17.6); `hold` n=47 +2.130% and `trail` n=62 +1.066% carry
the book, `sl` n=30 −4.092% leaks it. The audit's own kill condition is the
question this instrument exists to ask: ARE the 1–4h losers merely the stops —
selection on OUTCOME, a band that is losing by definition of the exit that
ended it — or would holding through the first hours have turned them?

METHOD — entries HELD CONSTANT, the (gx) discipline.
  1. THE LEDGER SPLIT, recomputed through the grader's owners (`edge_audit
     .shape` -> `golive_readiness.stats`): hold band × exit reason × lens, plus
     the diagnostic the audit did not print — what share of each band is an
     `sl` exit. A band that is 80% stops is a stop's P&L wearing a clock.
  2. THE COUNTERFACTUAL WALK on the book's OWN closes inside the recorded scout
     tape (5-min `lighter-market` marks, 200h from the public bus): every real
     entry (its own coin, side, entry price, open time) is walked forward
     through `lighter_ticket_taker.exit_reason` — the SAME rule object the bot
     runs, with the trend bars for breakout lenses and the row's own stamped
     bracket for the reversion lens — once with the shipped rule (floor 0) and
     once per floor F in FLOORS_H, during which no `tp`/`sl`/`trail` may fire
     (the peak still ratchets, so the trail after the floor is measured from
     the true peak). Survivors at the tape's end are marked at the last mark
     (the IMB-10 rule: a floor cannot "win" by deferring a loss off the tape).
  3. THE CALIBRATION GATE ((gx)): the floor-0 walk must reproduce the realised
     closes — mean gap within CALIB_TOL_PP — or the instrument REFUSES to
     recommend and prints its numbers labelled REFUSED. A 5-min tape against a
     90-s loop leaves a small, honest residual; a large one means the walk is
     not the bot.
  4. THE VERDICT is the PAIRED delta per floor (floor − shipped, same entries),
     with its lower bound at `fleet_allocation.t_crit(n)` and both halves.

THE PRE-REGISTERED RULE (`PRE_REGISTERED`, since 2026-09-02): a floor F is
ADOPTED (shadow-first, as a registered lever with its own cage) only on
FRESH closes opened after `since`, at n >= MIN_N, when the paired delta's
lower bound is > 0 AND both halves of the delta are >= 0 AND the calibration
gate passed; REFUTED at n >= MIN_N when the paired delta's upper bound is
<= 0 for every floor. Else NOT DECIDABLE. Judged against the book's OWN
shipped rule on the same entries — never against the hold band that
motivated it (I25: a band selected on an outcome is a biased estimator by
construction).

WHAT IT DOES NOT DO: it changes no exit, registers no lever, resets no era.
`TT_MIN_HOLD_H` does not exist and this study does not create it — a CONFIRMED
read is the argument for one, recorded as its own act.

THE HONEST LIMIT: `breakoutup` is the lens the finding lives on, and the
replay's up-resolver needs the venue's candle endpoint, which this session's
egress policy refuses (403). The WALK does not need it — it starts from real
entries — which is why the counterfactual here is ledger-anchored rather than
a `lighter_ticket_replay` run. The replay form is the right instrument for a
floor's effect on ENTRIES it would free (a position held longer blocks a slot)
and belongs in the container; that half is declared, not done.

    python3 scripts/study_taker_hold_floor_2026-09-02.py                      # public feeds (200h tape)
    python3 scripts/study_taker_hold_floor_2026-09-02.py --ledger t.json --tape-json tape.json
    python3 scripts/study_taker_hold_floor_2026-09-02.py --selftest           # offline, pure
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (HERE, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import edge_audit as ea                  # noqa: E402
import fleet_allocation as fa            # noqa: E402
import golive_readiness as gr            # noqa: E402
import lighter_ticket_taker as tt        # noqa: E402

DASH = "https://pnl-dashboard-production-858c.up.railway.app"
TAKER = "lighter-ticket-taker-lshadow"
TAPE_KEY = "lighter-market"
MAX_HOURS = 200
FLOORS_H = [4.0, 8.0, 12.0, 24.0]
CALIB_TOL_PP = 0.60          # mean |walked − realised|, percentage points (the divergence study's bar)
MIN_N = 30
TREND_LENSES = ("breakout", "breakoutup")

PRE_REGISTERED = {
    "id": "taker-hold-floor",
    "since": "2026-09-02T09:30:00+00:00",
    "min_n": MIN_N, "floors_h": FLOORS_H, "calib_tol_pp": CALIB_TOL_PP,
    "rule": ("ADOPT floor F (shadow-first, its own registered lever) only on "
             "closes opened after `since`, n>=MIN_N, when the PAIRED delta "
             "(F − shipped, same entries) has lower bound > 0 at t_crit(n) AND "
             "both halves >= 0 AND the calibration gate passed; REFUTE at "
             "n>=MIN_N when every floor's paired upper bound <= 0; else NOT "
             "DECIDABLE."),
    "kill": ("the 1–4h losers are the stops — a floor that turns them costs "
             "more on the ones that keep falling than it earns on the ones "
             "that turn; visible as a paired delta whose lower bound never "
             "clears zero"),
    "motivating_numbers": {"1-3d": "+2.219%/t t=+3.06 n=57", "1-4h": "-2.595% t=-3.19 n=20",
                           "source": "EDGE_AUDIT_2026-09-02.md §2"},
}


# ---------------------------------------------------------------- loading

def _get(url, timeout=400):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _ts(s):
    d = ea._ts(s)
    if d is not None and d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d


def normalise_tape(items):
    """[(dt, marks)] oldest-first; snapshots without marks dropped."""
    out = []
    for it in items or []:
        if not isinstance(it, dict):
            continue
        p = it.get("payload") if isinstance(it.get("payload"), dict) else it
        dt = _ts(it.get("ts") or p.get("updated"))
        marks = p.get("marks")
        if dt is None or not isinstance(marks, dict) or not marks:
            continue
        out.append((dt, marks))
    out.sort(key=lambda x: x[0])
    return out


def load_tape(path=None, bus_json=None, hours=MAX_HOURS):
    if path:
        with open(path) as fh:
            raw = json.load(fh)
        items = raw.get("history") if isinstance(raw, dict) else raw
        items = [x for x in (items or []) if not isinstance(x, dict) or x.get("key") in (None, TAPE_KEY)]
        return normalise_tape(items), "file"
    if os.environ.get("DATABASE_URL"):
        import bot_pnl_store as store
        hist = store.fetch_state_history(TAPE_KEY, limit=6000) or []
        return normalise_tape(list(reversed(hist))), "db"
    d = _get(f"{bus_json or DASH + '/bus.json'}?hours={int(min(hours, MAX_HOURS))}")
    return normalise_tape([x for x in (d.get("history") or []) if x.get("key") == TAPE_KEY]), "bus"


# ---------------------------------------------------------------- the ledger split

def _grade(quads):
    rows = [(q[0], q[1], q[2]) for q in quads]
    s = gr.stats(rows) if len(rows) >= 2 else {"n": len(rows)}
    out = {"n": s.get("n", 0), "usd": round(sum(q[1] for q in quads), 2)}
    if s.get("se_pct") is not None:
        crit = fa.t_crit(s["n"])
        m, se = 100 * s["mean_pct"], 100 * s["se_pct"]
        out.update(mean_pct=round(m, 4), t=round(s["t"], 3),
                   lb_pct=round(m - crit * se, 4), ub_pct=round(m + crit * se, 4))
    return out


def ledger_split(quads):
    """hold band × exit × lens through the grader's own stats, plus the
    'what share of this band is a stop' diagnostic."""
    by_band, by_band_exit, by_lens_band = defaultdict(list), defaultdict(list), defaultdict(list)
    for q in quads:
        r, o = q[7], _ts(q[3])
        if o is None:
            continue
        band = ea.hold_bucket((q[2] - o).total_seconds() / 3600)
        by_band[band].append(q)
        by_band_exit[(band, ea.exit_of(r))].append(q)
        by_lens_band[(ea.setup_of(r) or "(none)", band)].append(q)
    bands = {b: _grade(v) for b, v in by_band.items()}
    for b, v in by_band.items():
        ex = Counter(ea.exit_of(q[7]) for q in v)
        bands[b]["exits"] = dict(ex)
        bands[b]["sl_share"] = round(ex.get("sl", 0) / len(v), 3)
    return {"bands": bands,
            "band_exit": {f"{b}|{e}": _grade(v) for (b, e), v in by_band_exit.items()},
            "lens_band": {f"{l}|{b}": _grade(v) for (l, b), v in by_lens_band.items()}}


# ---------------------------------------------------------------- the walk

def bars_for(r):
    """((tp, sl, hold_h), trail) the position was governed by — the trend
    exit for breakout lenses (the BULL_MODE routing, forced here so an env
    default of off cannot silently grade the fixed bracket), else the row's
    OWN stamped bracket, else the module's."""
    lens = ea.setup_of(r)
    if lens in TREND_LENSES:
        return (999.0, tt.BRK_SL, tt.BRK_MAX_HOLD_H), tt.BRK_TRAIL
    st = ((r.get("extra") or {}).get("bars") or {}) if isinstance(r.get("extra"), dict) else {}
    try:
        return (float(st.get("tp", tt.TAKE_PROFIT)), float(st.get("sl", tt.STOP_LOSS)),
                float(st.get("max_hold_h", tt.MAX_HOLD_H))), 0.0
    except (TypeError, ValueError):
        return (tt.TAKE_PROFIT, tt.STOP_LOSS, tt.MAX_HOLD_H), 0.0


def walk(path, entry, opened, is_long, bars, trail, floor_h=0.0):
    """(reason, exit_mark, exit_dt, hours_held) through `tt.exit_reason` over
    `path` = [(dt, mark)] strictly after `opened`. During the first `floor_h`
    hours no tp/sl/trail may fire; the peak still ratchets. ('open', last
    mark, last dt, h) when the tape ends first — never a silent drop."""
    sgn = 1.0 if is_long else -1.0
    peak = 0.0
    last = None
    for dt, mark in path:
        if dt <= opened or not mark:
            continue
        last = (dt, mark)
        r = (mark / entry - 1.0) * sgn
        peak = max(peak, r)
        if (dt - opened).total_seconds() < floor_h * 3600:
            continue
        reason = tt.exit_reason(entry, mark, opened, dt, is_long, bars=bars,
                                peak_ret=peak if trail else None, trail=trail)
        if reason:
            return reason, mark, dt, (dt - opened).total_seconds() / 3600
    if last is None:
        return None, None, None, None
    return "open", last[1], last[0], (last[0] - opened).total_seconds() / 3600


def counterfactual(quads, tape, floors=FLOORS_H, since=None):
    """Every close inside the tape window, walked shipped-vs-floor."""
    if not tape:
        return {"n": 0, "why": "no tape"}
    t_lo, t_hi = tape[0][0], tape[-1][0]
    paths = defaultdict(list)
    for dt, marks in tape:
        for sym, m in marks.items():
            try:
                paths[sym].append((dt, float(m)))
            except (TypeError, ValueError):
                continue
    per = []
    skipped = Counter()
    for q in quads:
        r, o = q[7], _ts(q[3])
        if o is None or o < t_lo or o > t_hi:
            skipped["outside-tape"] += 1
            continue
        if since is not None and o <= since:
            skipped["before-since"] += 1
            continue
        side = ea.side_of(r)
        sym = str(q[6] or "").split("/")[0]
        if side is None or sym not in paths:
            skipped["no-side" if side is None else "no-marks"] += 1
            continue
        entry = r.get("entry_price")
        if not isinstance(entry, (int, float)) or entry <= 0:
            nxt = [m for dt, m in paths[sym] if dt >= o]
            if not nxt:
                skipped["no-entry"] += 1
                continue
            entry = nxt[0]
        bars, trail = bars_for(r)
        is_long = side == "long"
        sgn = 1.0 if is_long else -1.0
        row = {"sym": sym, "lens": ea.setup_of(r), "side": side, "opened": o.isoformat(),
               "realised_pct": 100 * float(q[0]), "realised_exit": ea.exit_of(r)}
        reason, mark, dt, h = walk(paths[sym], entry, o, is_long, bars, trail, 0.0)
        if reason is None:
            skipped["no-path"] += 1
            continue
        row["shipped"] = {"pct": 100 * (mark / entry - 1) * sgn, "exit": reason, "h": round(h, 2)}
        for f in floors:
            reason, mark, dt, h = walk(paths[sym], entry, o, is_long, bars, trail, f)
            row[f"floor_{f:g}"] = {"pct": 100 * (mark / entry - 1) * sgn, "exit": reason, "h": round(h, 2)}
        per.append(row)
    out = {"n": len(per), "skipped": dict(skipped), "floors_h": list(floors),
           "tape_span": [t_lo.isoformat(), t_hi.isoformat()], "rows": per}
    if not per:
        return out
    gap = [abs(x["shipped"]["pct"] - x["realised_pct"]) for x in per]
    out["calibration"] = {"mean_abs_gap_pp": round(sum(gap) / len(gap), 4),
                          "mean_shipped_pct": round(sum(x["shipped"]["pct"] for x in per) / len(per), 4),
                          "mean_realised_pct": round(sum(x["realised_pct"] for x in per) / len(per), 4),
                          "exit_agreement": round(sum(1 for x in per if x["shipped"]["exit"] == x["realised_exit"]) / len(per), 3),
                          "tol_pp": CALIB_TOL_PP}
    out["calibration"]["ok"] = abs(out["calibration"]["mean_shipped_pct"]
                                   - out["calibration"]["mean_realised_pct"]) <= CALIB_TOL_PP
    out["by_floor"] = {}
    for f in floors:
        d = [x[f"floor_{f:g}"]["pct"] - x["shipped"]["pct"] for x in per]
        out["by_floor"][f"{f:g}h"] = paired(d, [x[f"floor_{f:g}"]["exit"] for x in per])
    return out


def paired(deltas, exits=None):
    n = len(deltas)
    m = sum(deltas) / n
    o = {"n": n, "mean_delta_pp": round(m, 4)}
    if n >= 2:
        sd = math.sqrt(sum((x - m) ** 2 for x in deltas) / n) or 1e-12
        se = sd / math.sqrt(n)
        crit = fa.t_crit(n)
        o.update(t=round(m / se, 3), lb_pp=round(m - crit * se, 4), ub_pp=round(m + crit * se, 4),
                 h1=round(sum(deltas[: n // 2]), 3), h2=round(sum(deltas[n // 2:]), 3),
                 wins=sum(1 for x in deltas if x > 0), losses=sum(1 for x in deltas if x < 0))
    if exits:
        o["exits"] = dict(Counter(exits))
    return o


def decide(cf, min_n=MIN_N):
    """The PRE_REGISTERED rule on a counterfactual result. Pure."""
    n = cf.get("n", 0)
    if n < min_n:
        return {"verdict": "not_decidable", "why": f"n={n} < {min_n} walked closes"}
    if not (cf.get("calibration") or {}).get("ok"):
        return {"verdict": "refused", "why": "calibration gate failed — the walk is not the bot"}
    best, best_f = None, None
    all_refuted = True
    for f, p in (cf.get("by_floor") or {}).items():
        if p.get("ub_pp") is None:
            continue
        if p["ub_pp"] > 0:
            all_refuted = False
        if p.get("lb_pp", -1) > 0 and p.get("h1", -1) >= 0 and p.get("h2", -1) >= 0:
            if best is None or p["lb_pp"] > best["lb_pp"]:
                best, best_f = p, f
    if best is not None:
        return {"verdict": "confirmed", "floor": best_f,
                "why": f"paired delta lb {best['lb_pp']:+.3f}pp > 0, halves {best['h1']:+.2f}/{best['h2']:+.2f}"}
    if all_refuted:
        return {"verdict": "refuted", "why": "every floor's paired upper bound <= 0"}
    return {"verdict": "undecided", "why": "no floor clears lb>0 with both halves; not all excluded"}


def run(shaped, tape, since=None):
    d = shaped.get(TAKER) or {"rows": []}
    quads = d["rows"]
    cf = counterfactual(quads, tape, since=since)
    return {"registered": PRE_REGISTERED, "book": TAKER,
            "n_era": len(quads), "ledger_split": ledger_split(quads),
            "counterfactual": {k: v for k, v in cf.items() if k != "rows"},
            "walked": cf.get("rows", []), "decision": decide(cf)}


def render(res):
    L = [f"# taker hold-floor study — pre-registered, read-only · era n={res['n_era']}",
         "", "## ledger split by hold band (the audit's cut, recomputed through the grader)",
         "| band | n | mean% | t | lb% | $ | sl share | exits |", "|---|---:|---:|---:|---:|---:|---:|---|"]
    order = ["<1h", "1-4h", "4-24h", "1-3d", "3-7d", ">7d", "?"]
    for b in order:
        g = res["ledger_split"]["bands"].get(b)
        if g:
            L.append(f"| {b} | {g['n']} | {g.get('mean_pct', '—')} | {g.get('t', '—')} | {g.get('lb_pct', '—')} | "
                     f"{g['usd']} | {g['sl_share']} | {g['exits']} |")
    cf = res["counterfactual"]
    L += ["", f"## counterfactual walk · tape {cf.get('tape_span')} · walked n={cf.get('n')} · skipped {cf.get('skipped')}"]
    cal = cf.get("calibration")
    if cal:
        L.append(f"calibration: shipped-walk mean {cal['mean_shipped_pct']:+.3f}% vs realised "
                 f"{cal['mean_realised_pct']:+.3f}% · per-trade |gap| {cal['mean_abs_gap_pp']:.3f}pp · "
                 f"exit agreement {cal['exit_agreement']:.0%} · {'OK' if cal['ok'] else 'REFUSED'} (tol {cal['tol_pp']}pp)")
        L += ["", "| floor | n | paired Δ pp | t | lb | ub | h1 | h2 | W/L | exits |", "|---|---:|---:|---:|---:|---:|---:|---:|---|---|"]
        for f, p in cf["by_floor"].items():
            L.append(f"| {f} | {p['n']} | {p['mean_delta_pp']:+.3f} | {p.get('t', '—')} | {p.get('lb_pp', '—')} | "
                     f"{p.get('ub_pp', '—')} | {p.get('h1', '—')} | {p.get('h2', '—')} | {p.get('wins', '—')}/{p.get('losses', '—')} | {p.get('exits')} |")
    L += ["", f"VERDICT: {res['decision']['verdict']} — {res['decision']['why']}"]
    return "\n".join(L)


# ---------------------------------------------------------------- selftest

def _synth_tape(t0, sym_paths, step_min=5):
    """sym_paths: {sym: [price at t0 + k*step]} -> tape [(dt, marks)]."""
    n = max(len(v) for v in sym_paths.values())
    tape = []
    for k in range(n):
        marks = {s: p[min(k, len(p) - 1)] for s, p in sym_paths.items()}
        tape.append((t0 + timedelta(minutes=k * step_min), marks))
    return tape


def _quad(sym, opened, closed, pct, reason, entry, extra=None):
    r = {"pair": f"{sym}/USDC", "side": "long", "reason": reason, "entry_price": entry,
         "opened_at": opened.isoformat(), "closed_at": closed.isoformat(), "extra": extra}
    return (pct, pct * 100, closed, opened.isoformat(), extra, reason, f"{sym}/USDC", r)


def _selftest():
    t0 = datetime(2026, 9, 1, tzinfo=timezone.utc)
    # TURN: dips to -8% (through the -7% trend stop) at 1h, rallies to +12% by
    # 6h, gives back 6% -> shipped = sl at 1h; floor 4h = trail well in profit.
    turn = [100.0] * 12 + [92.0] * 12 + [96, 100, 104, 108, 112] + [112.0] * 40 + [105.0] * 3 + [105.0] * 200
    # FALL: -8% at 1h and keeps falling -> shipped = sl; floors lose MORE.
    fall = [100.0] * 12 + [92.0] * 12 + [88.0] * 24 + [84.0] * 24 + [80.0] * 220
    tape = _synth_tape(t0, {"TURN": turn, "FALL": fall})
    bars, trail = (999.0, tt.BRK_SL, tt.BRK_MAX_HOLD_H), tt.BRK_TRAIL
    o = t0 + timedelta(minutes=1)
    r0 = walk([(dt, m["TURN"]) for dt, m in tape], 100.0, o, True, bars, trail, 0.0)
    assert r0[0] == "sl" and r0[1] == 92.0, r0
    r4 = walk([(dt, m["TURN"]) for dt, m in tape], 100.0, o, True, bars, trail, 4.0)
    assert r4[0] == "trail" and r4[1] == 105.0 and r4[3] >= 4.0, r4
    f0 = walk([(dt, m["FALL"]) for dt, m in tape], 100.0, o, True, bars, trail, 0.0)
    f4 = walk([(dt, m["FALL"]) for dt, m in tape], 100.0, o, True, bars, trail, 4.0)
    assert f0[0] == "sl" and f0[1] == 92.0 and f4[0] == "sl" and f4[1] < 92.0, (f0, f4)
    # no look-ahead: nothing before the open is walked; an open past the tape is None
    assert walk([(dt, m["TURN"]) for dt, m in tape], 100.0, t0 + timedelta(days=9), True, bars, trail)[0] is None
    # the whole counterfactual: realised == shipped walk -> calibration OK;
    # a TURN-heavy ledger confirms a floor, a FALL-heavy one refutes it
    turns = [_quad("TURN", o, o + timedelta(hours=1), -0.08, "long-breakoutup_sl", 100.0) for _ in range(20)]
    falls = [_quad("FALL", o, o + timedelta(hours=1), -0.08, "long-breakoutup_sl", 100.0) for _ in range(20)]
    mixed = [q for pair in zip(turns, falls[:10] + turns[10:]) for q in pair]   # interleaved, both halves alike
    cf = counterfactual(mixed[:30], tape)
    assert cf["n"] == 30 and cf["calibration"]["ok"] and cf["calibration"]["mean_abs_gap_pp"] < 1e-6, cf["calibration"]
    assert cf["by_floor"]["4h"]["lb_pp"] > 0 and decide(cf)["verdict"] == "confirmed", (cf["by_floor"], decide(cf))
    cf2 = counterfactual([q for pair in zip(falls, turns[:3] + falls[3:]) for q in pair][:30], tape)
    assert cf2["by_floor"]["4h"]["ub_pp"] < 0 and decide(cf2)["verdict"] == "refuted", (cf2["by_floor"]["4h"], decide(cf2))
    # the calibration gate REFUSES a walk that does not reproduce the ledger
    bad = [_quad("TURN", o, o + timedelta(hours=1), +0.05, "long-breakoutup_tp", 100.0) for _ in range(30)]
    cfb = counterfactual(bad, tape)
    assert not cfb["calibration"]["ok"] and decide(cfb)["verdict"] == "refused", decide(cfb)
    # thin sample -> not decidable, never a verdict
    assert decide(counterfactual(turns[:5], tape))["verdict"] == "not_decidable"
    # a stamped reversion bracket is the row's own, the trend lens ignores it
    rr = {"reason": "short-divergence_tp", "extra": {"bars": {"tp": 0.05, "sl": -0.02, "max_hold_h": 24.0}}}
    assert bars_for(rr) == ((0.05, -0.02, 24.0), 0.0)
    assert bars_for({"reason": "long-breakoutup_trail"}) == ((999.0, tt.BRK_SL, tt.BRK_MAX_HOLD_H), tt.BRK_TRAIL)
    # the ledger split reads the band, the exit share and the lens
    sp = ledger_split(turns + falls)
    assert sp["bands"]["1-4h"]["n"] == 40 and sp["bands"]["1-4h"]["sl_share"] == 1.0
    assert "breakoutup|1-4h" in sp["lens_band"]
    assert PRE_REGISTERED["since"] and PRE_REGISTERED["min_n"] == MIN_N
    src = open(os.path.abspath(__file__)).read()
    for banned in ("write_levers", "get_lever(", "market_open", "save_state(", "publish("):
        assert src.count(banned) <= 1, banned      # the banned-list line itself
    print("study_taker_hold_floor selftest OK — walk (sl/trail/floor/no-look-ahead), "
          "positive control confirmed, falling control refuted, calibration gate refuses, "
          "thin sample not decidable, bars routing, ledger split, moves nothing")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ledger", help="local /trades.json?source=paper dump")
    ap.add_argument("--tape-json", help="local lighter-market history dump")
    ap.add_argument("--bus-json", help="bus.json base URL (default: the dashboard)")
    ap.add_argument("--hours", type=float, default=MAX_HOURS)
    ap.add_argument("--fresh", action="store_true", help="grade the registered fresh sample only")
    ap.add_argument("--json", help="write the full result here")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        _selftest()
        return 0
    tr = ea._load_json(a.ledger) if a.ledger else ea._get(f"{DASH}/trades.json?source=paper&limit=5000")
    trades = tr["trades"] if isinstance(tr, dict) else tr
    shaped = ea.shape(trades)
    tape, used = load_tape(a.tape_json, a.bus_json, a.hours)
    if not tape:
        print("REFUSING: no scout tape — nothing to walk (I1)")
        return 2
    since = _ts(PRE_REGISTERED["since"]) if a.fresh else None
    res = run(shaped, tape, since=since)
    res["tape_source"] = used
    print(render(res))
    if a.json:
        with open(a.json, "w") as fh:
            json.dump(res, fh, indent=1, default=str)
        print(f"\nwrote {a.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
