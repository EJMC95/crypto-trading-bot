#!/usr/bin/env python3
"""study_mum_noncrypto_sleeve_2026-09-02.py — is 👩 mum's NON-CRYPTO sleeve
losing, and has the sample earned the right to say so?

WHY. Eamon, 2-Sep: "How do we fix mum" / "if it makes any bot make more money
then implement." Her live arm's one measured weak spot on the day she was
asked about: the graded non-crypto sleeve (XAU / QQQ / SPY / XCU — the base
`NONCRYPTO_UNIVERSE`, gated by the per-asset oracle) read 7 closes at
−0.383%/trade (t −1.66), five of seven `max_hold` losers; the shadow twin
agrees (7 closes, −0.54%, t −2.38). The upper bound sits at zero. But 7 is
below the fleet's own 10-close computability floor (fleet_allocation.MIN_N):
a variance built from seven numbers cannot be repaired by a critical value
(I16, as amended (ua)). So the cut is REGISTERED, not applied.

THE MECHANISM the numbers point at, stated so the read tests a claim and not a
mood (I7): a tokenised equity or commodity book prints through its
underlying's CLOSED hours. A 1h RSI "oversold" read on a tape that is not
moving is a flat line, not a dip; the rebound the bracket is built for cannot
arrive before the underlying reopens, and the 24h cap books the position at a
loss. Crypto trades 24/7 and does not have this shape.

THE PRE-REGISTERED RULE (`PRE_REGISTERED`, since 2026-09-02): read at n>=10
non-crypto closes on the LIVE arm, or on 6-Sep, whichever first. CUT when the
live sleeve's upper bound (mean + t_crit(n)*SE) <= 0 AND the twin's sleeve
mean < 0 (two arms, one direction — the twin is the control and must agree
in sign; it is the same trades at a different size, so it is corroboration
of the mechanism, never a second independent sample); KEEP when the live
sleeve's mean > 0; else NOT DECIDABLE with n_req. The cut is
`FAMILY_NONCRYPTO_EXCLUDE="freqtrade-mum:<names>"` on BOTH hosts (per
carrier — the (vd) lesson: a change measured on one book must not re-aim two
others), reversible by unsetting it, era untouched (a universe edit is
ordinary tuning per (hc)).

Read-only: grades, moves nothing. Through the grader's owners
(`edge_audit.shape` -> `golive_readiness.era_rows`/`stats`,
`fleet_allocation.t_crit`, `fleet_bus.is_crypto`).

    python3 scripts/study_mum_noncrypto_sleeve_2026-09-02.py             # public feed
    python3 scripts/study_mum_noncrypto_sleeve_2026-09-02.py --ledger t.json
    python3 scripts/study_mum_noncrypto_sleeve_2026-09-02.py --selftest  # offline
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
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

DASH = "https://pnl-dashboard-production-858c.up.railway.app"
LIVE, SHADOW = "freqtrade-mum-lighter", "freqtrade-mum-lshadow"
MIN_N = int(getattr(fa, "MIN_N", 10))

PRE_REGISTERED = {
    "id": "mum-noncrypto-sleeve",
    "since": "2026-09-02T11:00:00+00:00",
    "min_n": MIN_N,
    "read_by": "2026-09-06",
    "rule": ("CUT when the LIVE non-crypto sleeve at n>=MIN_N has mean+t_crit*SE <= 0 "
             "AND the twin's non-crypto mean < 0; KEEP when the live sleeve mean > 0; "
             "else NOT DECIDABLE (publish n_req)."),
    "act": ("FAMILY_NONCRYPTO_EXCLUDE='freqtrade-mum:<names>' on mum-live AND "
            "family-lighter-shadow; era untouched; revert = unset"),
    "at_registration": {"live": "n=7 -0.383%/t t=-1.66 (5/7 max_hold)",
                        "shadow": "n=7 -0.540%/t t=-2.38 (5/7 max_hold)"},
    "mechanism": "closed-hours flat tape reads as oversold; the 24h cap books it at a loss",
}


def _is_crypto(coin):
    try:
        import fleet_bus as fb
        return bool(fb.is_crypto(coin))
    except Exception:            # noqa: BLE001
        return None


def _bounds(quads):
    rows = [(q[0], q[1], q[2]) for q in quads]
    s = gr.stats(rows) if len(rows) >= 2 else {"n": len(rows)}
    n = s.get("n", 0)
    out = {"n": n, "usd": round(sum(q[1] for q in quads), 2),
           "exits": dict(Counter(ea.exit_of(q[7]) for q in quads if len(q) > 7)),
           "coins": sorted({str(q[6]).split("/")[0] for q in quads})}
    if n < 2 or s.get("se_pct") is None:
        return out
    crit = fa.t_crit(n)
    m, se = 100 * s["mean_pct"], 100 * s["se_pct"]
    out.update(mean_pct=round(m, 4), t=round(s["t"], 3), se_pct=round(se, 4), crit=round(crit, 3),
               lb_pct=round(m - crit * se, 4), ub_pct=round(m + crit * se, 4),
               win=round(sum(1 for q in quads if q[0] > 0) / n, 3))
    return out


def split(quads, crypto=None):
    """{'crypto': [...], 'noncrypto': [...], 'unknown': [...]} by the venue's class."""
    out = defaultdict(list)
    for q in quads:
        coin = str(q[6] or "").split("/")[0]
        c = crypto.get(coin) if isinstance(crypto, dict) else _is_crypto(coin)
        out["crypto" if c else "noncrypto" if c is False else "unknown"].append(q)
    return out


def decide(live, twin, min_n=MIN_N):
    n = live.get("n", 0)
    if n < min_n or live.get("ub_pct") is None:
        t = abs(live.get("t") or 0.0)
        n_req = int(math.ceil(n * (fa.t_crit(max(n, 2)) / t) ** 2)) if t > 0.05 and n >= 2 else None
        return {"verdict": "not_decidable", "why": f"live sleeve n={n} < {min_n}", "n_req": n_req}
    if live["ub_pct"] <= 0 and (twin.get("mean_pct") or 0.0) < 0:
        return {"verdict": "cut", "why": f"live ub {live['ub_pct']:+.3f}% <= 0 on n={n}; twin mean {twin.get('mean_pct'):+.3f}% agrees"}
    if (live.get("mean_pct") or 0.0) > 0:
        return {"verdict": "keep", "why": f"live sleeve mean {live['mean_pct']:+.3f}% > 0"}
    return {"verdict": "undecided",
            "why": f"live ub {live['ub_pct']:+.3f}% > 0 or twin disagrees ({twin.get('mean_pct')})"}


def run(shaped, since=None, crypto=None):
    out = {"registered": PRE_REGISTERED, "arms": {}}
    for arm in (LIVE, SHADOW):
        quads = (shaped.get(arm) or {}).get("rows") or []
        if since is not None:
            quads = [q for q in quads if ea._ts(q[3]) and ea._ts(q[3]) > since]
        sp = split(quads, crypto)
        out["arms"][arm] = {k: _bounds(v) for k, v in sp.items()}
        out["arms"][arm]["n_total"] = len(quads)
    live = out["arms"][LIVE].get("noncrypto", {"n": 0})
    twin = out["arms"][SHADOW].get("noncrypto", {"n": 0})
    out["decision"] = decide(live, twin)
    return out


def render(res):
    L = ["# mum non-crypto sleeve — pre-registered read (read-only)"]
    for arm, d in res["arms"].items():
        L.append(f"\n## {arm} · n={d['n_total']}")
        L.append("| sleeve | n | mean% | t | ub% | win | $ | exits | coins |")
        L.append("|---|---:|---:|---:|---:|---:|---:|---|---|")
        for k in ("crypto", "noncrypto", "unknown"):
            g = d.get(k)
            if g and g.get("n"):
                L.append(f"| {k} | {g['n']} | {g.get('mean_pct', '—')} | {g.get('t', '—')} | {g.get('ub_pct', '—')} | "
                         f"{g.get('win', '—')} | {g['usd']} | {g['exits']} | {','.join(g['coins'])} |")
    L.append(f"\nVERDICT: {res['decision']['verdict']} — {res['decision']['why']}"
             + (f" (n_req {res['decision']['n_req']})" if res['decision'].get('n_req') else ""))
    return "\n".join(L)


# ---------------------------------------------------------------- selftest

def _quad(coin, pct, i, t0, reason="long-oversold-rebound_roi"):
    o = t0 + timedelta(hours=3 * i)
    c = o + timedelta(hours=6)
    r = {"pair": f"{coin}/USDC", "side": "long", "reason": reason, "opened_at": o.isoformat()}
    return (pct, pct * 100, c, o.isoformat(), None, reason, f"{coin}/USDC", r)


def _synth(seed, nc_mu, n_nc=12, n_c=40):
    rnd = random.Random(seed)
    t0 = datetime(2026, 9, 1, tzinfo=timezone.utc)
    rows = []
    for i in range(n_c):
        rows.append(_quad("BTC" if i % 2 else "SOL", rnd.gauss(0.006, 0.012), i, t0))
    for i in range(n_nc):
        rows.append(_quad(("XAU", "SPY", "QQQ", "XCU")[i % 4], rnd.gauss(nc_mu, 0.006), n_c + i, t0,
                          "long-oversold-rebound_max_hold"))
    rows.sort(key=lambda q: q[2])
    return rows


def _selftest():
    crypto = {"BTC": True, "SOL": True, "XAU": False, "SPY": False, "QQQ": False, "XCU": False}
    # POSITIVE CONTROL: a planted losing sleeve on both arms is CUT
    shaped = {LIVE: {"rows": _synth(1, -0.012)}, SHADOW: {"rows": _synth(2, -0.010)}}
    r = run(shaped, crypto=crypto)
    assert r["arms"][LIVE]["noncrypto"]["n"] == 12 and r["arms"][LIVE]["noncrypto"]["ub_pct"] < 0
    assert r["decision"]["verdict"] == "cut", r["decision"]
    assert r["arms"][LIVE]["noncrypto"]["exits"] == {"max_hold": 12}
    # PLACEBO: a flat sleeve is never cut
    r2 = run({LIVE: {"rows": _synth(3, 0.0)}, SHADOW: {"rows": _synth(4, 0.0)}}, crypto=crypto)
    assert r2["decision"]["verdict"] != "cut", r2["decision"]
    # a WINNING sleeve is KEPT
    r3 = run({LIVE: {"rows": _synth(5, 0.008)}, SHADOW: {"rows": _synth(6, 0.008)}}, crypto=crypto)
    assert r3["decision"]["verdict"] == "keep", r3["decision"]
    # THIN sample (the registration-day state): not decidable, with n_req
    r4 = run({LIVE: {"rows": _synth(7, -0.012, n_nc=7)}, SHADOW: {"rows": _synth(8, -0.012, n_nc=7)}}, crypto=crypto)
    assert r4["decision"]["verdict"] == "not_decidable" and r4["decision"]["n_req"], r4["decision"]
    # THE TWIN MUST AGREE: a live exclusion with a positive twin is undecided, never cut
    r5 = run({LIVE: {"rows": _synth(9, -0.012)}, SHADOW: {"rows": _synth(10, +0.010)}}, crypto=crypto)
    assert r5["decision"]["verdict"] == "undecided", r5["decision"]
    # the split never guesses a class: an unknown coin lands in `unknown`
    sp = split([_quad("ZZZ", 0.01, 0, datetime(2026, 9, 1, tzinfo=timezone.utc))], crypto={})
    assert list(sp) == ["unknown"]
    # `since` restricts to fresh opens
    r6 = run(shaped, since=datetime(2030, 1, 1, tzinfo=timezone.utc), crypto=crypto)
    assert r6["arms"][LIVE]["n_total"] == 0 and r6["decision"]["verdict"] == "not_decidable"
    assert PRE_REGISTERED["min_n"] == MIN_N and "CUT" in PRE_REGISTERED["rule"]
    with open(os.path.abspath(__file__)) as fh:
        src = fh.read()
    for banned in ("write_levers", "get_lever(", "market_open", "save_state(", "publish("):
        assert src.count(banned) <= 1, banned
    print("study_mum_noncrypto_sleeve selftest OK — planted sleeve CUT, placebo not, winner KEPT, "
          "thin not decidable, twin must agree, class never guessed, fresh split, moves nothing")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ledger")
    ap.add_argument("--fresh", action="store_true", help="grade closes OPENED after PRE_REGISTERED.since only")
    ap.add_argument("--json")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        _selftest()
        return 0
    tr = ea._load_json(a.ledger) if a.ledger else ea._get(f"{DASH}/trades.json?source=paper&limit=5000")
    trades = tr["trades"] if isinstance(tr, dict) else tr
    shaped = ea.shape(trades)
    since = ea._ts(PRE_REGISTERED["since"]) if a.fresh else None
    res = run(shaped, since=since)
    print(render(res))
    if a.json:
        with open(a.json, "w") as fh:
            json.dump(res, fh, indent=1, default=str)
    return 0


if __name__ == "__main__":
    sys.exit(main())
