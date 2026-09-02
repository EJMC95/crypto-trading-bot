#!/usr/bin/env python3
"""study_regime_short_veto_2026-09-02.py — the edge audit's hypothesis #3, as a
PRE-REGISTERED instrument: does a short opened while the oracle reads
`LONG-window` (or a long opened in `SHORT-window`) lose, on the fleet's OWN
ledger, and would a veto on it have raised the book's mean?

WHY (EDGE_AUDIT_2026-09-02.md §1b/§7). Every mixed book's in-era loss was its
SHORT side in a tape the oracle read as `risk-on uptrend`: 💸 farmer −0.640%/t
(t=−2.61, n=182), ⚖️ counterweight −4.044% (t=−2.79), 🛢️ garrett −2.409%
(t=−2.72), 🪁 kelly −0.410%. The audit ranked "a regime VETO on existing books'
shorts" as the highest-prior, lowest-cost hypothesis — a veto on books that
already exist, never a new one — and named its kill condition: the oracle lags
the regime by more than the books' hold. This is the test plan, written down
before the data is looked at, per I21 (a defence that lives only in prose has
not been written) and I25 (the counterfactual is the book's OWN mean, never
the window that motivated the change).

METHOD.
  * Sample: the paper ledger through the grader's own pipeline (identity
    imports from `edge_audit.shape`: `golive_readiness.era_rows`,
    `is_phantom_close`, `drop_retired_sleeves`, `bot_pnl_store.is_quarantined`)
    — the same rows the go-live gate grades, never the raw feed ((wo)).
  * Label: each close is labelled by the oracle's verdict for ITS coin at the
    last snapshot at or before its OPEN (no look-ahead — `verdict_at` binary-
    searches the history and refuses a snapshot after the open). A coin the
    oracle does not grade rides BTC's verdict if it is crypto (the family
    bot's own rule: crypto pairs ride the BTC gates — DECLARED, stamped
    `basis: btc-proxy`) and is UNKNOWN otherwise. A verdict older than
    MAX_GAP_S at the open is UNKNOWN. Unknown is reported, never guessed (I6).
  * `veto` = short in LONG-window or long in SHORT-window; `pass` = any other
    graded verdict. Each set is graded through `golive_readiness.stats` with
    the one-sided bounds at `fleet_allocation.t_crit(n)` — the (tz) power
    gate, the same critical value the retirement docket uses.

THE PRE-REGISTERED RULE (`PRE_REGISTERED` below, since 2026-09-02): a veto is
ADOPTED on a book only on closes opened AFTER `since`, when the vetoed set has
n >= MIN_N, its upper bound (mean + t_crit*SE) is <= 0 (the sample EXCLUDED a
positive mean), AND the passed set's mean is at or above the book's own mean
(the veto must not be removing the winners). It is REFUTED when the vetoed set
at n >= MIN_N has a lower bound >= 0, or reads at/above the passed set's mean
on >= 10 passed closes (the crowd was right). Anything else is NOT DECIDABLE
and publishes `n_req` — how many vetoed closes would settle it at the current
effect size. The rule is the same in both directions (I17: one standard of
evidence to doubt a thing and to feed it).

WHAT THIS DOES NOT DO: it vetoes nothing. It moves no lever, changes no book,
resets no era — a veto on the taker's sides would reset its 30-day clock (jf)
and the (wj) runbook forbids that before go-live. Acting on a CONFIRMED read
is a separate, recorded act, shadow-first, graded against the un-gated twin.

THE HONEST LIMIT, stated before the first run: the oracle read BTC LONG-window
in 418 of 418 snapshots over its whole reachable history (200h from the public
bus, 25-Aug -> 2-Sep), so on that window EVERY crypto short is in the veto set
and the `pass` set for crypto shorts is empty — the instrument can price the
vetoed set against the book's mean, and cannot yet price it against a passed
short. Per-asset verdicts DO vary (DOT/SUI SHORT-window 120 snapshots, META
265, TSLA 218, TAO/MSTR/COIN/QQQ/XAG mixed), so the non-proxy split exists on
those names. Coverage is published FIRST, per I1.

    python3 scripts/study_regime_short_veto_2026-09-02.py                 # public feeds
    python3 scripts/study_regime_short_veto_2026-09-02.py --ledger t.json --oracle-json o.json
    python3 scripts/study_regime_short_veto_2026-09-02.py --selftest      # offline, pure
"""
from __future__ import annotations

import argparse
import bisect
import json
import math
import os
import random
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (HERE, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import edge_audit as ea                  # noqa: E402  (shape/side_of — identity owners)
import fleet_allocation as fa            # noqa: E402  (t_crit)
import golive_readiness as gr            # noqa: E402  (stats/cluster_se)

DASH = "https://pnl-dashboard-production-858c.up.railway.app"
ORACLE_KEY = "regime-oracle"
MAX_GAP_S = 2 * 3600          # a verdict older than this at the open is UNKNOWN
MAX_HOURS = 200               # the public bus caps history at 200h
MIN_N = 30                    # the gate's own closes floor
MIN_PASS_N = 10               # fleet_allocation.MIN_N — a mean from fewer is not a mean
KNOWN = ("LONG-window", "SHORT-window", "dir-flat", "chop-gated")
VETO_MAP = {"short": "LONG-window", "long": "SHORT-window"}
PROXY = "BTC"

#: THE REGISTRATION — a commitment, not a re-derivation. Grade on closes
#: opened strictly after `since`; the numbers that motivated it are in the
#: edge audit and are NOT the sample this rule is graded on (I21/I25).
PRE_REGISTERED = {
    "id": "regime-short-veto",
    "since": "2026-09-02T09:30:00+00:00",
    "min_n": MIN_N,
    "rule": ("ADOPT (per book, shadow-first) when the vetoed set at n>=MIN_N "
             "has mean+t_crit*SE <= 0 AND the passed set's mean >= the book's "
             "own mean; REFUTE when the vetoed set at n>=MIN_N has "
             "mean-t_crit*SE >= 0, or reads >= the passed mean on >=10 passed "
             "closes; else NOT DECIDABLE (publish n_req)."),
    "kill": ("the oracle lags the regime by more than the books' hold — "
             "visible here as a vetoed set that is not worse than the passed "
             "set at the same n"),
    "motivating_numbers": {"farmer_short": "-0.640%/t t=-2.61 n=182",
                           "counterweight_short": "-4.044% t=-2.79",
                           "garrett_short": "-2.409% t=-2.72",
                           "source": "EDGE_AUDIT_2026-09-02.md §1b"},
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


def normalise_oracle(items):
    """[(dt, pairs, fleet_read)] oldest-first from raw history rows
    ({ts, payload}) — junk rows dropped, never guessed."""
    out = []
    for it in items or []:
        if not isinstance(it, dict):
            continue
        p = it.get("payload") if isinstance(it.get("payload"), dict) else it
        dt = _ts(it.get("ts") or p.get("updated") or p.get("updated_at"))
        pairs = p.get("pairs")
        if dt is None or not isinstance(pairs, dict):
            continue
        out.append((dt, pairs, (p.get("fleet") or {}).get("read")))
    out.sort(key=lambda x: x[0])
    return out


def load_oracle(path=None, bus_json=None, hours=MAX_HOURS):
    """The oracle's verdict history: a saved JSON, else the DB (in a
    container), else the public bus (`?hours=`, capped at 200h)."""
    if path:
        with open(path) as fh:
            raw = json.load(fh)
        items = raw.get("history") if isinstance(raw, dict) else raw
        items = [x for x in (items or []) if not isinstance(x, dict)
                 or x.get("key") in (None, ORACLE_KEY)]
        return normalise_oracle(items), "file"
    if os.environ.get("DATABASE_URL"):
        import bot_pnl_store as store
        hist = store.fetch_state_history(ORACLE_KEY, limit=5000) or []
        return normalise_oracle(list(reversed(hist))), "db"
    d = _get(f"{bus_json or DASH + '/bus.json'}?hours={int(min(hours, MAX_HOURS))}")
    items = [x for x in (d.get("history") or []) if x.get("key") == ORACLE_KEY]
    return normalise_oracle(items), "bus"


# ---------------------------------------------------------------- labelling

def _is_crypto(sym):
    try:
        import fleet_bus as fb
        return bool(fb.is_crypto(sym))
    except Exception:            # noqa: BLE001 — offline: the venue class is unknown
        return None


def verdict_at(oracle, coin, dt, crypto=None, max_gap_s=MAX_GAP_S):
    """(verdict, basis) for `coin` at `dt` from the LAST snapshot at or before
    it — never one after (no look-ahead). basis: 'own' | 'btc-proxy';
    (None, why) when the oracle cannot say."""
    if not oracle or dt is None:
        return None, "no-oracle"
    times = [o[0] for o in oracle]
    i = bisect.bisect_right(times, dt) - 1
    if i < 0:
        return None, "before-history"
    snap_dt, pairs, _ = oracle[i]
    if (dt - snap_dt).total_seconds() > max_gap_s:
        return None, "stale-verdict"
    v = (pairs.get(coin) or {}).get("verdict") if isinstance(pairs.get(coin), dict) else None
    if v in KNOWN:
        return v, "own"
    is_c = _is_crypto(coin) if crypto is None else crypto
    if is_c:
        pv = (pairs.get(PROXY) or {}).get("verdict") if isinstance(pairs.get(PROXY), dict) else None
        if pv in KNOWN:
            return pv, "btc-proxy"
    return None, "ungraded-coin"


def label(side, verdict):
    """'veto' | 'pass' | None."""
    if side not in VETO_MAP or verdict not in KNOWN:
        return None
    return "veto" if VETO_MAP[side] == verdict else "pass"


# ---------------------------------------------------------------- grading

def _bounds(quads):
    """{n, mean_pct, t, se_pct, lb_pct, ub_pct, usd, t_cluster} through the
    grader's own `stats`; bounds at `fleet_allocation.t_crit(n)`. Percent."""
    rows = [(q[0], q[1], q[2]) for q in quads]
    s = gr.stats(rows) if len(rows) >= 2 else {"n": len(rows)}
    n = s.get("n", 0)
    out = {"n": n, "usd": round(sum(q[1] for q in quads), 2)}
    if n < 2 or s.get("se_pct") is None:
        return out
    crit = fa.t_crit(n)
    m, se = 100 * s["mean_pct"], 100 * s["se_pct"]
    out.update(mean_pct=round(m, 4), t=round(s["t"], 3), se_pct=round(se, 4),
               crit=round(crit, 3), lb_pct=round(m - crit * se, 4),
               ub_pct=round(m + crit * se, 4))
    keys = [(str(q[6]).split("/")[0], q[2].date().isoformat()) for q in quads]
    se_cr, g, _ = gr.cluster_se([q[0] for q in quads], keys)
    out["t_cluster"] = round(s["mean_pct"] / se_cr, 3) if se_cr else None
    out["n_clusters"] = g
    return out


def decide(veto, pas, book_mean_pct, min_n=MIN_N):
    """The PRE_REGISTERED rule, applied to two graded sets. Pure."""
    n = veto.get("n", 0)
    if n < min_n or veto.get("ub_pct") is None:
        t = abs(veto.get("t") or 0.0)
        n_req = (int(math.ceil(n * (fa.t_crit(max(n, 2)) / t) ** 2)) if t > 0.05 and n >= 2
                 else None)
        return {"verdict": "not_decidable",
                "why": f"vetoed n={n} < {min_n}" if n < min_n else "vetoed set ungradeable",
                "n_req": n_req}
    pass_ok = pas.get("n", 0) >= MIN_PASS_N and pas.get("mean_pct") is not None
    if veto["ub_pct"] <= 0 and (book_mean_pct is None or not pass_ok
                                or pas["mean_pct"] >= book_mean_pct):
        return {"verdict": "confirmed",
                "why": (f"vetoed upper bound {veto['ub_pct']:+.3f}% <= 0 on n={n}"
                        + (f"; passed mean {pas['mean_pct']:+.3f}% >= book {book_mean_pct:+.3f}%"
                           if pass_ok and book_mean_pct is not None else
                           "; passed set too thin to contradict"))}
    if veto.get("lb_pct", -1) >= 0 or (pass_ok and veto["mean_pct"] >= pas["mean_pct"]):
        return {"verdict": "refuted",
                "why": (f"vetoed lower bound {veto['lb_pct']:+.3f}% >= 0"
                        if veto.get("lb_pct", -1) >= 0 else
                        f"vetoed mean {veto['mean_pct']:+.3f}% >= passed {pas['mean_pct']:+.3f}%")}
    return {"verdict": "undecided",
            "why": f"vetoed ub {veto['ub_pct']:+.3f}% > 0 and lb {veto['lb_pct']:+.3f}% < 0 at n={n}"}


def grade_book(bot, quads, oracle, since=None, crypto=None):
    """One book: coverage FIRST (I1), then the two sets, then the rule.
    `since` (datetime) restricts to closes OPENED after it — the fresh sample
    the registration is graded on."""
    sets = defaultdict(list)
    unknown = defaultdict(int)
    basis = defaultdict(int)
    by_side = defaultdict(lambda: defaultdict(list))
    n_total = 0
    for q in quads:
        r = q[7] if len(q) > 7 else {}
        opened = _ts(q[3])
        if since is not None and (opened is None or opened <= since):
            continue
        n_total += 1
        side = ea.side_of(r)
        coin = str(q[6] or "").split("/")[0]
        v, why = verdict_at(oracle, coin, opened, crypto=crypto)
        lab = label(side, v)
        if lab is None:
            unknown["no-side" if side is None else why] += 1
            continue
        basis[why] += 1
        sets[lab].append(q)
        by_side[side][lab].append(q)
    labelled = sum(len(v) for v in sets.values())
    veto, pas = _bounds(sets["veto"]), _bounds(sets["pass"])
    book = _bounds(quads if since is None else [q for q in quads
                                                 if _ts(q[3]) and _ts(q[3]) > since])
    out = {"bot": bot, "n": n_total, "labelled": labelled,
           "coverage": round(labelled / n_total, 3) if n_total else None,
           "unknown": dict(unknown), "basis": dict(basis),
           "book": book, "veto": veto, "pass": pas,
           "by_side": {s: {k: _bounds(v) for k, v in d.items()} for s, d in by_side.items()},
           "decision": decide(veto, pas, book.get("mean_pct"))}
    # the counterfactual, stated as $ and as the mean the book would have had
    if sets["veto"] and pas.get("n", 0) >= 2:
        out["if_vetoed"] = {"mean_pct": pas.get("mean_pct"), "n": pas.get("n"),
                            "usd_forgone": veto.get("usd"),
                            "delta_mean_pp": (round(pas["mean_pct"] - book["mean_pct"], 4)
                                              if book.get("mean_pct") is not None else None)}
    return out


def run(shaped, oracle, since=None, bots=None):
    out = {"registered": PRE_REGISTERED, "oracle": {
        "n_snapshots": len(oracle),
        "span": ([oracle[0][0].isoformat(), oracle[-1][0].isoformat()] if oracle else None),
        "btc_verdicts": _count_verdicts(oracle, PROXY)},
        "books": {}}
    for bot, d in sorted(shaped.items()):
        if bots and bot not in bots:
            continue
        out["books"][bot] = grade_book(bot, d["rows"], oracle, since=since)
    return out


def _count_verdicts(oracle, coin):
    c = defaultdict(int)
    for _, pairs, _ in oracle:
        v = (pairs.get(coin) or {}).get("verdict") if isinstance(pairs.get(coin), dict) else None
        c[str(v)] += 1
    return dict(c)


def render(res):
    L = ["# regime short-veto study — pre-registered, read-only",
         f"oracle: {res['oracle']['n_snapshots']} snapshots {res['oracle']['span']} · "
         f"BTC verdicts {res['oracle']['btc_verdicts']}",
         "", "| book | n | cover | veto n | veto mean% | ub% | t_cl | pass n | pass mean% | book mean% | verdict |",
         "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    for bot, b in res["books"].items():
        v, p, k = b["veto"], b["pass"], b["book"]
        L.append(f"| {bot} | {b['n']} | {b['coverage']} | {v.get('n', 0)} | "
                 f"{v.get('mean_pct', '—')} | {v.get('ub_pct', '—')} | {v.get('t_cluster', '—')} | "
                 f"{p.get('n', 0)} | {p.get('mean_pct', '—')} | {k.get('mean_pct', '—')} | "
                 f"{b['decision']['verdict']}: {b['decision']['why']} |")
    return "\n".join(L)


# ---------------------------------------------------------------- selftest

def _synth(seed=7, n=120, flip_at_h=60, planted=True):
    """A two-regime oracle and a ledger whose short P&L depends on the regime
    at OPEN (planted) — or on nothing (placebo)."""
    rnd = random.Random(seed)
    t0 = datetime(2026, 9, 1, tzinfo=timezone.utc)
    oracle = []
    for h in range(0, 121):
        v = "LONG-window" if h < flip_at_h else "SHORT-window"
        oracle.append((t0 + timedelta(hours=h), {"BTC": {"verdict": v},
                                                  "DOT": {"verdict": "SHORT-window"}}, "x"))
    quads = []
    for i in range(n):
        opened = t0 + timedelta(hours=rnd.uniform(0.5, 119.5))
        side = "short" if i % 2 == 0 else "long"
        regime = "LONG-window" if (opened - t0).total_seconds() < flip_at_h * 3600 else "SHORT-window"
        against = (side == "short" and regime == "LONG-window") or (side == "long" and regime == "SHORT-window")
        mu = (-0.012 if against else 0.010) if planted else 0.0
        pct = rnd.gauss(mu, 0.012)
        closed = opened + timedelta(hours=rnd.uniform(1, 12))
        r = {"side": side, "reason": f"{side}-x_hold", "pair": "ETH/USDC"}
        quads.append((pct, pct * 100, closed, opened.isoformat(), None, r["reason"], "ETH/USDC", r))
    quads.sort(key=lambda q: q[2])
    return oracle, quads


def _selftest():
    t0 = datetime(2026, 9, 1, tzinfo=timezone.utc)
    oracle, quads = _synth()
    # labelling: no look-ahead, stale verdict is unknown, proxy is declared
    assert verdict_at(oracle, "ETH", t0 - timedelta(seconds=1), crypto=True) == (None, "before-history")
    assert verdict_at(oracle, "ETH", t0 + timedelta(hours=59, minutes=59), crypto=True) == ("LONG-window", "btc-proxy")
    assert verdict_at(oracle, "ETH", t0 + timedelta(hours=60), crypto=True) == ("SHORT-window", "btc-proxy")
    assert verdict_at(oracle, "DOT", t0 + timedelta(hours=1), crypto=True) == ("SHORT-window", "own")
    assert verdict_at(oracle, "SPY", t0 + timedelta(hours=1), crypto=False) == (None, "ungraded-coin")
    assert verdict_at(oracle, "ETH", t0 + timedelta(hours=125), crypto=True) == (None, "stale-verdict")
    assert label("short", "LONG-window") == "veto" and label("long", "LONG-window") == "pass"
    assert label("long", "SHORT-window") == "veto" and label("short", "dir-flat") == "pass"
    assert label(None, "LONG-window") is None and label("short", "junk") is None
    # POSITIVE CONTROL: a planted regime effect is CONFIRMED by the rule
    g = grade_book("synth", quads, oracle, crypto=True)
    assert g["coverage"] == 1.0 and g["unknown"] == {}, g
    assert g["veto"]["ub_pct"] < 0 < g["pass"]["lb_pct"], (g["veto"], g["pass"])
    assert g["decision"]["verdict"] == "confirmed", g["decision"]
    assert g["if_vetoed"]["delta_mean_pp"] > 0
    # PLACEBO: no planted effect -> never confirmed (the instrument does not
    # manufacture a veto), and the rule reads refuted/undecided/not_decidable
    _, placebo = _synth(seed=11, planted=False)
    gp = grade_book("placebo", placebo, oracle, crypto=True)
    assert gp["decision"]["verdict"] != "confirmed", gp["decision"]
    # SHUFFLED LABELS: the planted ledger against a shuffled oracle loses it
    rnd = random.Random(3)
    shuffled = [(dt, {"BTC": {"verdict": rnd.choice(["LONG-window", "SHORT-window"])}}, "x")
                for dt, _, _ in oracle]
    gs = grade_book("shuffled", quads, shuffled, crypto=True)
    assert abs(gs["veto"]["mean_pct"] - gs["pass"]["mean_pct"]) < abs(g["veto"]["mean_pct"] - g["pass"]["mean_pct"]) / 2
    # the fresh split: `since` after every open leaves nothing to grade
    ge = grade_book("empty", quads, oracle, since=t0 + timedelta(days=30), crypto=True)
    assert ge["n"] == 0 and ge["decision"]["verdict"] == "not_decidable"
    # the rule's arms, driven directly
    assert decide({"n": 5}, {"n": 0}, 0.1)["verdict"] == "not_decidable"
    assert decide({"n": 40, "ub_pct": -0.1, "lb_pct": -0.9, "mean_pct": -0.5, "t": -2.5},
                  {"n": 40, "mean_pct": 0.3}, 0.1)["verdict"] == "confirmed"
    assert decide({"n": 40, "ub_pct": -0.1, "lb_pct": -0.9, "mean_pct": -0.5, "t": -2.5},
                  {"n": 40, "mean_pct": 0.0}, 0.1)["verdict"] == "undecided", "passed below book mean"
    assert decide({"n": 40, "ub_pct": 0.9, "lb_pct": 0.1, "mean_pct": 0.5, "t": 2.5},
                  {"n": 40, "mean_pct": 0.3}, 0.1)["verdict"] == "refuted"
    assert decide({"n": 40, "ub_pct": 0.2, "lb_pct": -0.2, "mean_pct": 0.0, "t": 0.0},
                  {"n": 40, "mean_pct": -0.1}, 0.1)["verdict"] == "refuted", "crowd was right"
    nd = decide({"n": 12, "ub_pct": 0.2, "lb_pct": -0.6, "mean_pct": -0.2, "t": -1.0}, {"n": 0}, 0.1)
    assert nd["verdict"] == "not_decidable" and nd["n_req"] and nd["n_req"] > 12
    # normalise tolerates junk and orders by time
    raw = [{"ts": "2026-09-01T02:00:00+00:00", "payload": {"pairs": {"BTC": {"verdict": "LONG-window"}}}},
           {"ts": "junk", "payload": {"pairs": {}}}, "nope",
           {"ts": "2026-09-01T01:00:00+00:00", "payload": {"pairs": {"BTC": {"verdict": "dir-flat"}}}}]
    no = normalise_oracle(raw)
    assert [o[0].hour for o in no] == [1, 2]
    # the registration carries the commitment fields
    assert PRE_REGISTERED["since"] and PRE_REGISTERED["min_n"] == MIN_N and "ADOPT" in PRE_REGISTERED["rule"]
    # the instrument moves nothing
    with open(os.path.abspath(__file__)) as fh:
        src = fh.read()
    for banned in ("write_levers", "get_lever(", "market_open", "save_state(", "publish("):
        assert banned not in src.replace('("write_levers", "get_lever(", "market_open", "save_state(", "publish(")', ""), banned
    print("study_regime_short_veto selftest OK — labelling (no look-ahead, stale/unknown, "
          "btc-proxy declared), positive control confirmed, placebo not confirmed, "
          "shuffled labels lose the effect, every arm of the pre-registered rule, moves nothing")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ledger", help="local /trades.json?source=paper dump")
    ap.add_argument("--limit", type=int, default=5000,
                    help="ledger row cap; a count equal to it is REFUSED as truncation ((qz))")
    ap.add_argument("--oracle-json", help="local regime-oracle history dump")
    ap.add_argument("--bus-json", help="bus.json base URL (default: the dashboard)")
    ap.add_argument("--hours", type=float, default=MAX_HOURS)
    ap.add_argument("--since", help="ISO stamp: grade only closes OPENED after it (default: none)")
    ap.add_argument("--pooled", action="store_true",
                    help="grade the WHOLE window instead of the registered fresh sample — NOT the registered read")
    ap.add_argument("--bots", help="comma list of books to grade (default: all)")
    ap.add_argument("--json", help="write the full result here")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        _selftest()
        return 0
    # [(xh)] through edge_audit's ONE loader, so the (qz) truncation refusal
    # applies here too — a row count equal to the cap is a sampled ledger.
    trades = ea.load_trades(a.ledger, a.limit)
    shaped = ea.shape(trades)
    oracle, used = load_oracle(a.oracle_json, a.bus_json, a.hours)
    if not oracle:
        print("REFUSING: no oracle history — nothing to label against (I1)")
        return 2
    # [(xh)] THE REGISTERED READ IS THE FRESH ONE, BY DEFAULT — I21 as
    # amended at (tt): a pre-registered bucket is decided on closes taken
    # AFTER registration, never by re-mining the window that generated it.
    # `--pooled` is the explicit opt-out and is NOT the registered read.
    since = (_ts(a.since) if a.since else None) if a.pooled else _ts(PRE_REGISTERED["since"])
    if a.pooled:
        print("NOTE: --pooled — this is the motivating window, not the registered read (I21).")
    res = run(shaped, oracle, since=since, bots=set(a.bots.split(",")) if a.bots else None)
    res["oracle"]["source"] = used
    res["since"] = since.isoformat() if since else None
    print(render(res))
    if a.json:
        with open(a.json, "w") as fh:
            json.dump(res, fh, indent=1, default=str)
        print(f"\nwrote {a.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
