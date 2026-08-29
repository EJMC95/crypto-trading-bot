#!/usr/bin/env python3
"""Fleet-wide entry/exit/stop/loss audit with far-vs-close diagnostics.

"Eagle + gecko" lens: FAR (whole ledger) and CLOSE (recent closes) for every
book on the feed, with optimization advisories per book.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import statistics
import urllib.request

DASH = "https://pnl-dashboard-production-858c.up.railway.app"
STOP_SUFFIXES = (
    "sl", "stop", "stop_loss", "trailing_stop_loss", "trail", "ghoststop",
    "hard_stop", "catastrophic_stop",
)


def fetch_json(path_or_url: str):
    try:
        if path_or_url.startswith("http"):
            req = urllib.request.Request(
                path_or_url, headers={"User-Agent": "fleet-entry-exit-audit"}
            )
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        with open(path_or_url) as f:
            return json.load(f)
    except Exception:
        return None


def parse_ts(ts):
    try:
        return dt.datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except Exception:
        return None


def exit_reason(row: dict) -> str:
    r = str(row.get("reason") or "").strip()
    if r:
        return r
    tag = str(row.get("tag") or "").strip()
    if not tag:
        return "?"
    return tag.rsplit("_", 1)[-1] if "_" in tag else tag


def is_stop_reason(reason: str) -> bool:
    tail = str(reason or "").rsplit("_", 1)[-1].lower()
    whole = str(reason or "").lower()
    return tail in STOP_SUFFIXES or any(whole.endswith("_" + s) for s in STOP_SUFFIXES)


def hold_h(row: dict):
    a = parse_ts(row.get("opened_at"))
    b = parse_ts(row.get("closed_at"))
    if a is None or b is None:
        return None
    h = (b - a).total_seconds() / 3600.0
    return h if h >= 0 else None


def _f(x):
    try:
        return float(x)
    except Exception:
        return None


def reason_stats(rows: list[dict]):
    per = {}
    for r in rows:
        k = exit_reason(r)
        per.setdefault(k, []).append(r)
    out = {}
    for reason, g in per.items():
        pnls = [_f(x.get("pnl_abs")) for x in g]
        pnls = [x for x in pnls if x is not None]
        pcts = [_f(x.get("pnl_pct")) for x in g]
        pcts = [x for x in pcts if x is not None]
        hs = [hold_h(x) for x in g]
        hs = [x for x in hs if x is not None]
        out[reason] = {
            "n": len(g),
            "usd": sum(pnls),
            "mean_pct": (statistics.mean(pcts) * 100.0) if pcts else None,
            "hold_h": statistics.median(hs) if hs else None,
        }
    return out


def hold_ratio(stats):
    earners = [k for k, v in stats.items() if v["usd"] > 0]
    losers = [k for k, v in stats.items() if v["usd"] < 0]
    if not earners or not losers:
        return None
    top_e = max(earners, key=lambda k: stats[k]["usd"])
    top_l = min(losers, key=lambda k: stats[k]["usd"])
    he = stats[top_e]["hold_h"]
    hl = stats[top_l]["hold_h"]
    if not he or not hl or hl <= 0:
        return None
    return he / hl


def slice_stats(rows: list[dict]):
    pnls = [_f(r.get("pnl_abs")) for r in rows]
    pnls = [x for x in pnls if x is not None]
    pcts = [_f(r.get("pnl_pct")) for r in rows]
    pcts = [x for x in pcts if x is not None]
    rs = reason_stats(rows)
    stop = [
        v for k, v in rs.items()
        if is_stop_reason(k)
    ]
    return {
        "n": len(rows),
        "usd": sum(pnls),
        "mean_pct": statistics.mean(pcts) * 100.0 if pcts else None,
        "single_exit": len(rs) == 1 and bool(rs),
        "hold_ratio": hold_ratio(rs),
        "stop_n": sum(v["n"] for v in stop),
        "stop_usd": sum(v["usd"] for v in stop),
    }


def advisories(far, close):
    out = []
    if far["n"] == 0:
        return ["no closes yet — feed entries first, then re-grade exits/stops"]
    if far["single_exit"] and far["usd"] < 0:
        out.append("single-exit losing profile — add/validate secondary exit path")
    if far["stop_n"] >= 5 and far["stop_usd"] < 0:
        out.append("stops are net negative — run stop-reclaim + exit sweep for this book")
    if far["hold_ratio"] is not None and far["hold_ratio"] >= 3.0:
        out.append("top loser exits far earlier than top earner — likely thesis cut too early")
    if close["n"] >= 10 and far["mean_pct"] is not None and close["mean_pct"] is not None:
        if close["mean_pct"] < far["mean_pct"] - 0.2:
            out.append("recent window weaker than long window — investigate entry quality drift")
    if not out:
        out.append("no high-confidence red flag from this lens")
    return out


def impact_score(row: dict) -> float:
    far = row["far"]
    close = row["close"]
    score = 0.0
    if far["n"] == 0:
        return 0.0
    if far["single_exit"] and far["usd"] < 0:
        score += 2.0
    if far["stop_n"] >= 5 and far["stop_usd"] < 0:
        score += min(4.0, abs(far["stop_usd"]) / 2.0)
    if far["hold_ratio"] is not None and far["hold_ratio"] >= 3.0:
        score += min(3.0, (far["hold_ratio"] - 2.0))
    if close["n"] >= 10 and far["mean_pct"] is not None and close["mean_pct"] is not None:
        drift = far["mean_pct"] - close["mean_pct"]
        if drift > 0.2:
            score += min(3.0, drift * 4.0)
    return round(score, 3)


def top_issues(rows: list[dict], limit=10):
    ranked = []
    for r in rows:
        s = impact_score(r)
        if s <= 0:
            continue
        ranked.append({"bot": r["bot"], "impact": s, "advisories": r["advisories"]})
    ranked.sort(key=lambda x: (-x["impact"], x["bot"]))
    return ranked[:max(1, int(limit))]


def bot_rows(trades):
    out = {}
    for r in trades or []:
        b = r.get("bot")
        if not b:
            continue
        out.setdefault(b, []).append(r)
    for b in out:
        out[b] = sorted(
            out[b],
            key=lambda x: parse_ts(x.get("closed_at")) or dt.datetime.min.replace(tzinfo=dt.timezone.utc),
        )
    return out


def run_audit(pnl, trades, close_n=30):
    active = sorted({(b or {}).get("bot") for b in (pnl or {}).get("bots", []) if (b or {}).get("bot")})
    by_bot = bot_rows(trades)
    rows = []
    for bot in active:
        series = by_bot.get(bot, [])
        far = slice_stats(series)
        close = slice_stats(series[-close_n:])
        rows.append({
            "bot": bot,
            "far": far,
            "close": close,
            "advisories": advisories(far, close),
            "impact": impact_score({"far": far, "close": close}),
        })
    return rows


def render(rows, close_n=30):
    out = []
    out.append("# Fleet entry/exit/stop/loss audit")
    out.append("")
    out.append(f"Eagle lens = full history; Gecko lens = last {close_n} closes.")
    out.append("")
    out.append("| bot | impact | far n | far $ | far mean% | close n | close $ | close mean% | stop $ far | hold ratio far | advisories |")
    out.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for r in sorted(rows, key=lambda x: (-x["impact"], x["bot"])):
        f = r["far"]
        c = r["close"]
        fm = "—" if f["mean_pct"] is None else f"{f['mean_pct']:+.3f}"
        cm = "—" if c["mean_pct"] is None else f"{c['mean_pct']:+.3f}"
        hr = "—" if f["hold_ratio"] is None else f"{f['hold_ratio']:.2f}x"
        adv = "; ".join(r["advisories"][:2])
        out.append(
            f"| {r['bot']} | {r['impact']:.2f} | {f['n']} | {f['usd']:+.2f} | {fm} | {c['n']} | {c['usd']:+.2f} | {cm} | {f['stop_usd']:+.2f} | {hr} | {adv} |"
        )
    ranked = top_issues(rows, limit=5)
    if ranked:
        out.append("")
        out.append("## Highest-impact issues")
        out.append("")
        for i, r in enumerate(ranked, 1):
            out.append(f"{i}. `{r['bot']}` impact={r['impact']:.2f} — {r['advisories'][0]}")
    return "\n".join(out) + "\n"


def _by_bot(rows):
    return {str((r or {}).get("bot")): r for r in rows or [] if (r or {}).get("bot")}


def render_before_after(before_rows, after_rows):
    b = _by_bot(before_rows)
    a = _by_bot(after_rows)
    bots = sorted(set(b) | set(a))
    out = []
    out.append("# Before vs after")
    out.append("")
    out.append("| bot | impact before | impact after | Δ impact | far $ before | far $ after | Δ far $ | close mean% before | close mean% after |")
    out.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for bot in bots:
        br = b.get(bot)
        ar = a.get(bot)
        bi = 0.0 if not br else float(br.get("impact") or 0.0)
        ai = 0.0 if not ar else float(ar.get("impact") or 0.0)
        bf = 0.0 if not br else float((br.get("far") or {}).get("usd") or 0.0)
        af = 0.0 if not ar else float((ar.get("far") or {}).get("usd") or 0.0)
        bcm = None if not br else (br.get("close") or {}).get("mean_pct")
        acm = None if not ar else (ar.get("close") or {}).get("mean_pct")
        bcm_t = "—" if bcm is None else f"{float(bcm):+.3f}"
        acm_t = "—" if acm is None else f"{float(acm):+.3f}"
        out.append(
            f"| {bot} | {bi:.2f} | {ai:.2f} | {ai - bi:+.2f} | {bf:+.2f} | {af:+.2f} | {af - bf:+.2f} | {bcm_t} | {acm_t} |"
        )
    return "\n".join(out) + "\n"


def selftest():
    now = dt.datetime(2026, 1, 10, tzinfo=dt.timezone.utc)
    def row(bot, reason, pnl, pct, open_h, close_h):
        return {
            "bot": bot,
            "reason": reason,
            "pnl_abs": pnl,
            "pnl_pct": pct,
            "opened_at": (now + dt.timedelta(hours=open_h)).isoformat(),
            "closed_at": (now + dt.timedelta(hours=close_h)).isoformat(),
        }

    t = []
    for i in range(20):
        t.append(row("b1", "decay_paid", 2.0, 0.01, i, i + 60))
    for i in range(30):
        t.append(row("b1", "short_flip", -1.0, -0.004, i, i + 8))
    for i in range(12):
        t.append(row("b1", "short_sl", -0.5, -0.003, i, i + 1))
    t.append(row("b2", "only_exit", -1.0, -0.01, 0, 10))
    p = {"bots": [{"bot": "b1"}, {"bot": "b2"}, {"bot": "b3"}]}
    rows = run_audit(p, t, close_n=10)
    d = {r["bot"]: r for r in rows}
    assert d["b1"]["far"]["n"] == 62
    assert d["b1"]["far"]["hold_ratio"] and d["b1"]["far"]["hold_ratio"] >= 3.0
    assert d["b1"]["far"]["stop_n"] == 12 and d["b1"]["far"]["stop_usd"] < 0
    assert any("stops are net negative" in a for a in d["b1"]["advisories"])
    assert any("single-exit losing profile" in a for a in d["b2"]["advisories"])
    assert d["b3"]["far"]["n"] == 0
    assert d["b3"]["advisories"][0].startswith("no closes yet")
    tops = top_issues(rows, limit=2)
    assert tops and tops[0]["bot"] == "b1"
    before_after = render_before_after(rows, rows)
    assert "| b1 |" in before_after and "Δ impact" in before_after
    print("study_entry_exit_stoploss_fleet selftest OK")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--pnl-json", default=f"{DASH}/pnl.json")
    ap.add_argument("--trades-json", default=f"{DASH}/trades.json?source=paper&limit=5000")
    ap.add_argument("--close-n", type=int, default=30)
    ap.add_argument("--json-out", default=None)
    ap.add_argument("--compare-before", default=None)
    ap.add_argument("--compare-after", default=None)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    if args.compare_before and args.compare_after:
        with open(args.compare_before) as f:
            b = json.load(f)
        with open(args.compare_after) as f:
            a = json.load(f)
        print(render_before_after(b.get("rows") or [], a.get("rows") or []))
        return 0
    pnl = fetch_json(args.pnl_json) or {}
    trades_payload = fetch_json(args.trades_json) or {}
    trades = trades_payload if isinstance(trades_payload, list) else (trades_payload.get("trades") or [])
    rows = run_audit(pnl, trades, close_n=max(1, args.close_n))
    txt = render(rows, close_n=max(1, args.close_n))
    print(txt)
    if args.json_out:
        with open(args.json_out, "w") as f:
            json.dump({"rows": rows, "close_n": max(1, args.close_n)}, f, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
