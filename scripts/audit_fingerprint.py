#!/usr/bin/env python3
"""audit_fingerprint.py — PROVE the protected surface did not move.

    python3 audit_fingerprint.py --save   BEFORE any Phase 3/4 work
    python3 audit_fingerprint.py --check  AFTER

The brief lists five symbols that must not be modified (SLOW_LOOP,
STALE_SECONDS, EXPECTED, LABELS, CURRENT_BOTS) and requires that existing bot
P&Ls be verified unchanged after testing. "I did not touch it" is an assertion;
a hash is a measurement. This makes the claim falsifiable.

TWO SURFACES, deliberately separate:
  * REPO  — the five symbols' source text, extracted by AST so a comment or a
    reformat elsewhere in the file cannot mask a real edit (and cannot raise a
    false one either).
  * LEDGER — every bot's realised P&L and close count from the paper ledger.
    Read-only. A change here after a read-only audit means something WROTE,
    which is the condition this exists to catch.

The ledger moves on its own because the fleet keeps trading, so a bot whose
close COUNT rose is reported as `traded`, not `mutated`. What must never change
is a bot's P&L at a FIXED close count — so the check compares the first N
closes, N being the count at save time. That is the only comparison that
separates "the fleet traded" from "someone rewrote history".
"""
from __future__ import annotations
import argparse, ast, hashlib, json, sys

PROTECTED = ["SLOW_LOOP", "STALE_SECONDS", "EXPECTED", "LABELS", "CURRENT_BOTS"]
DASH = "pnl_dashboard.py"


def symbol_source(path, names):
    src = open(path).read()
    tree = ast.parse(src)
    lines = src.splitlines(keepends=True)
    out = {}
    for node in ast.walk(tree):
        tgts = []
        if isinstance(node, ast.Assign):
            tgts = [t.id for t in node.targets if isinstance(t, ast.Name)]
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            tgts = [node.target.id]
        for t in tgts:
            if t in names:
                seg = "".join(lines[node.lineno - 1:node.end_lineno])
                out[t] = {"sha256": hashlib.sha256(seg.encode()).hexdigest(),
                          "lineno": node.lineno, "n_lines": node.end_lineno - node.lineno + 1,
                          "bytes": len(seg)}
    return out


def ledger_fingerprint(trades):
    """bot -> {n, pnl_sum, sha of the first-n (trade_id, pnl) pairs in order}."""
    by = {}
    for t in trades:
        by.setdefault(t.get("bot"), []).append(t)
    out = {}
    for bot, rows in by.items():
        rows.sort(key=lambda r: (str(r.get("closed_at")), str(r.get("trade_id"))))
        h = hashlib.sha256()
        s = 0.0
        for r in rows:
            h.update(("%s|%.10f|" % (r.get("trade_id"), float(r.get("pnl_abs") or 0))).encode())
            s += float(r.get("pnl_abs") or 0)
        out[bot] = {"n": len(rows), "pnl_sum": round(s, 6), "sha256": h.hexdigest()}
    return out


def prefix_sha(trades, bot, n):
    rows = [t for t in trades if t.get("bot") == bot]
    rows.sort(key=lambda r: (str(r.get("closed_at")), str(r.get("trade_id"))))
    h = hashlib.sha256(); s = 0.0
    for r in rows[:n]:
        h.update(("%s|%.10f|" % (r.get("trade_id"), float(r.get("pnl_abs") or 0))).encode())
        s += float(r.get("pnl_abs") or 0)
    return h.hexdigest(), round(s, 6), len(rows)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", required=True)
    ap.add_argument("--state", required=True, help="fingerprint json path")
    ap.add_argument("--save", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    raw = json.load(open(a.ledger))
    trades = raw.get("trades", raw) if isinstance(raw, dict) else raw
    now = {"symbols": symbol_source(DASH, PROTECTED), "ledger": ledger_fingerprint(trades)}
    missing = [s for s in PROTECTED if s not in now["symbols"]]
    if missing:
        print("FAIL: protected symbol(s) not found: %s" % missing); return 2
    if a.save:
        json.dump(now, open(a.state, "w"), indent=1)
        print("SAVED %d symbols, %d bots, %d closes" %
              (len(now["symbols"]), len(now["ledger"]), len(trades)))
        return 0
    old = json.load(open(a.state))
    bad, traded = [], []
    for s in PROTECTED:
        o, n = old["symbols"].get(s, {}), now["symbols"][s]
        if o.get("sha256") != n["sha256"]:
            bad.append("SYMBOL MUTATED: %s (was %s.. now %s..)"
                       % (s, str(o.get('sha256'))[:12], n["sha256"][:12]))
    for bot, o in old["ledger"].items():
        if bot not in now["ledger"]:
            bad.append("BOT VANISHED from ledger: %s" % bot); continue
        sha, s, total = prefix_sha(trades, bot, o["n"])
        if sha != o["sha256"]:
            bad.append("P&L REWRITTEN: %s — first %d closes changed (sum %s -> %s)"
                       % (bot, o["n"], o["pnl_sum"], s))
        elif total > o["n"]:
            traded.append("%s +%d closes" % (bot, total - o["n"]))
    print("PROTECTED SYMBOLS: %d/%d unchanged" % (len(PROTECTED) - len([b for b in bad if 'SYMBOL' in b]), len(PROTECTED)))
    print("BOT LEDGERS: %d checked, %d rewritten" % (len(old["ledger"]), len([b for b in bad if 'REWRITTEN' in b or 'VANISHED' in b])))
    if traded:
        print("traded since save (expected, not a defect): %s" % ", ".join(sorted(traded)))
    for b in bad:
        print("  !! " + b)
    print("VERDICT: " + ("CLEAN — nothing protected moved" if not bad else "DIRTY"))
    return 2 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
