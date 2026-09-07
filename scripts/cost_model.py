#!/usr/bin/env python3
"""scripts/cost_model.py — WHAT EXECUTION ACTUALLY COSTS EACH BOOK.

    python3 scripts/cost_model.py --ledger t.json --feed p.json --bus b.json \
        --obd obd.json --books books.json --out cost.json --md COST_MODEL.md
    python3 scripts/cost_model.py --selftest

WHY, and it starts by CORRECTING THIS AUDIT'S OWN PHASE-2 OUTPUT. The baseline
stressed every book at the fleet-wide `MEASURED_RT_BPS` (17.49) and reported
that it "flips two profitable books negative" — 🌾 carry +$12.92 -> -$2.82 and
🔮 georgia v1 +$12.85 -> -$10.59. **Two things were wrong with reading that as
a cost verdict, and both are structural rather than arithmetic:**

  1. **17.49 IS A MEAN OVER A RIGHT-SKEWED DISTRIBUTION.** Measured here on 711
     recorded spreads across 40 coins, the median full quoted spread by volume
     band runs **17.79bps at $0.01-0.3M/day down to 2.50bps above $5.7M/day** —
     a 7x span, monotone, fitting `spread ~ vol^-0.503` (the square-root
     liquidity law, R^2 0.386 per-trade). One fleet mean charged to every book
     is the wrong number for all of them: it overcharges the liquid books and
     UNDERCHARGES the thin ones, which is the dangerous direction.

  2. **THE BOOKS ALREADY PAY.** Every living book's realised P&L is already net
     of execution, by one of two mechanisms this module DERIVES rather than
     assumes (see `fill_basis`). Charging the fleet mean ON TOP is not a cost
     verdict — it is a double charge. 🌾 carry is the clearest case: its P&L is
     literally `accrued - fees` (`funding_carry_bot` lines 1291/1379), so the
     stress deducted a round trip it had already deducted.

**SO THE USEFUL QUESTION IS NOT "what would it cost?" BUT "how much headroom is
there between what it already pays and what would kill it?"** That is
`breakeven_cost_bps` / `cost_headroom_x`, which `edge_audit` already owns; this
module supplies the missing half — the per-book CURRENT cost to compare them
against, measured on the book's own basket at the book's own deployed clip.

IT RE-IMPLEMENTS NOTHING. The round-trip arithmetic is
`funding_carry_bot.rt_cost_bps` — the fleet's declared ONE OWNER of "measured
adverse cost of getting `notional` IN and OUT, in bps of mid", which
`scripts/study_depth_vs_volume.py` already imports rather than copying. The
book walk underneath it is `venues.shadow.fill_from_book`, i.e. the same code
that fills the shadow books, so the cost model and the fills cannot disagree.
The sample is `edge_audit.shape` (era, phantom filter, quarantine) and the
row->file map is `scripts/fleet_books.ROW_ENTRY`.

THE CALIBRATION GATE. Two books record the venue's quoted spread on every fill
(🪁 kelly `spread_bps_entry` on 590 closes, 🧘 douglas entry AND exit on 83).
This module fetches live books for the coins they traded and REFUSES unless its
own top-of-book spread reproduces those recorded medians within tolerance.
Distributional, not per-trade: the records are historical and the fetch is now,
so an exact match is not available and claiming one would be the fiction. A
book that cannot reproduce what the fleet already recorded may not price what
it did not.

UNMEASURED IS NULL. An unfillable clip, an empty book, a coin with no fetch:
all None, never 0.0 and never a large number. A cost that reads FREE would
authorise exactly the books this exists to warn about, and a cost that reads
INFINITE would retire them — both are verdicts the data did not support.
"""
from __future__ import annotations

import argparse
import ast
import datetime as _dt
import json
import math
import os
import statistics as st
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import edge_audit                      # noqa: E402 — sample + symbol owner
import fleet_books                     # noqa: E402 — row -> entry file
import funding_carry_bot as _carry      # noqa: E402 — THE round-trip owner

rt_cost_bps = _carry.rt_cost_bps

API = os.environ.get("LIGHTER_API", "https://mainnet.zklighter.elliot.ai")

#: Calibration tolerance, in bps, on the |fetched - recorded| median spread per
#: book. Wide enough that an hour's tape roll does not fail it, tight enough
#: that fetching the wrong market or mis-sorting the book does. Sorting is the
#: real hazard: `venues/lighter_client._rest_book` records that REST snapshots
#: come back UNSORTED while every consumer takes [0] as top-of-book.
CALIB_TOL_BPS = float(os.environ.get("COST_CALIB_TOL_BPS", "8.0"))

#: Coins fetched, most-traded first. A governed budget, not a limit on the
#: answer: coverage is PUBLISHED per book, and a book whose basket is not
#: covered gets None rather than an average of the coins that happened to fit.
FETCH_TOP_N = int(os.environ.get("COST_FETCH_TOP_N", "70"))


# ----------------------------------------------------------------- fill basis
def fill_basis_of_file(path):
    """`book_walked` / `modelled_flat` / None for one file. The shared core of
    `fill_basis`, split out so a wrapper can be resolved through its import
    without a second copy of the detection rule."""
    try:
        with open(path) as fh:
            src = fh.read()
        tree = ast.parse(src)
    except (OSError, SyntaxError):
        return None
    names = {"ShadowBroker", "venue_context", "fill_from_book"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and any(al.name in names
                                                    for al in node.names):
            return "book_walked"
        if isinstance(node, ast.Name) and node.id in names:
            return "book_walked"
        if isinstance(node, ast.Attribute) and node.attr in names:
            return "book_walked"
    if any(k in src for k in ("SLIP_COST", "HEDGE_COST", "RT_COST_FRAC")):
        return "modelled_flat"
    return None



def fill_basis(bot, root=".", venue=None):
    """How this book's P&L ALREADY accounts for execution. DERIVED, not typed.

    Read from the book's own entry file via `fleet_books.ROW_ENTRY`, because
    which mechanism a book uses is a property of the REPO and a hand-kept table
    of it would rot on the next book that changes broker (the (mn) lesson).

      * `real_fills`   — a REAL-MONEY row: the prices in the ledger are what
        the exchange actually filled, so the cost is not modelled at all, it
        was paid. Derived from the PAYLOAD (`extra.venue == lighter_live`),
        never from the file — which rows are live is a property of the payload
        and must not be written down (`scripts/fleet_books` says so, and the
        audit-scope rule has rotted on a slot swap four times).
      * `book_walked`  — fills come from `ShadowBroker`, which walks the LIVE
        order book, so the crossed spread is INSIDE `entry_price`/`exit_price`
        and therefore inside `pnl_abs`. Nothing further is deducted. Reached
        directly OR through `venues.venue_context`, which resolves to that
        broker in every shadow mode — a book does not stop walking the book
        because it asked a factory for its broker.
      * `modelled_flat` — fills are taken at mark and a flat per-side constant
        (`SLIP_COST`, `HEDGE_COST`) is deducted explicitly. The charge is a
        CONSTANT, so it is exact only at the clip it was calibrated for —
        `fleet_bus` records this as "fiction at 6.7x it".
      * `unknown` — the file could not be read or names neither mechanism.
        DECLARED, never guessed: I8/I6 both say an absence is not a finding.
    """
    if venue == "lighter_live":
        return {"basis": "real_fills", "entry": fleet_books.ROW_ENTRY.get(bot),
                "note": "prices are actual exchange fills — cost was PAID, not "
                        "modelled; the live-vs-twin gap is `impl_shortfall`"}
    entry = fleet_books.ROW_ENTRY.get(bot)
    if not entry:
        return {"basis": "unknown", "why": "row not in fleet_books.ROW_ENTRY"}
    path = os.path.join(root, entry)
    try:
        with open(path) as fh:
            src = fh.read()
    except OSError as e:
        return {"basis": "unknown", "why": "unreadable:%s" % type(e).__name__}
    # AST over imports/names, not a substring scan — a page-wide grep matches
    # the word inside a docstring that DENIES using it ((po)'s rule).
    # AST over imports and names. `venue_context` counts: it is the factory
    # that HANDS a book its broker, and in every shadow mode that broker is
    # ShadowBroker — the first cut missed 3 books by matching only the class,
    # which is the (po) lesson (a check that inspects the wrong thing reports
    # clean) landing inside this very module.
    WALK_NAMES = {"ShadowBroker", "venue_context", "fill_from_book"}
    walked = False
    try:
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.ImportFrom):
                walked = walked or any(al.name in WALK_NAMES for al in node.names)
            elif isinstance(node, ast.Name) and node.id in WALK_NAMES:
                walked = True
            elif isinstance(node, ast.Attribute) and node.attr in WALK_NAMES:
                walked = True
    except SyntaxError:
        return {"basis": "unknown", "why": "unparseable"}
    flat = any(k in src for k in ("SLIP_COST", "HEDGE_COST", "RT_COST_FRAC"))
    if not walked and not flat:
        # ONE HOP through a wrapper. 🚀 bezos is `import lighter_book_douglas_bot
        # as core` plus env defaults — its fill mechanism is its core's, and
        # reading only the wrapper reported `unknown` for a book whose basis is
        # perfectly knowable. One hop, not a walk: a recursive import chase
        # would drag the whole tree in and is not what a wrapper is.
        for node in ast.walk(ast.parse(src)):
            mods = []
            if isinstance(node, ast.Import):
                mods = [al.name for al in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                mods = [node.module]
            for m in mods:
                if not (m.startswith("lighter_") or m.startswith("funding_")):
                    continue
                inner = os.path.join(root, m.replace(".", os.sep) + ".py")
                if not os.path.exists(inner):
                    continue
                sub = fill_basis_of_file(inner)
                if sub:
                    return {"basis": sub, "entry": entry, "via": m,
                            "note": "derived through the wrapper's core module"}
    if walked:
        return {"basis": "book_walked", "entry": entry,
                "note": "crossed spread is inside the fill price, so inside pnl_abs"}
    if flat:
        return {"basis": "modelled_flat", "entry": entry,
                "note": "flat per-side constant deducted at mark; exact only "
                        "at the clip it was calibrated for"}
    return {"basis": "unknown", "entry": entry,
            "why": "names neither ShadowBroker nor a flat cost constant"}


# --------------------------------------------------------------- the baskets
def baskets(shaped, bots):
    """{bot: {coin: n_trades}} over each book's ERA sample — what it trades."""
    out = {}
    for b in bots:
        rows = (shaped.get(b) or {}).get("rows") or []
        d = {}
        for q in rows:
            c = edge_audit.base_symbol(q[6])
            if c:
                d[c] = d.get(c, 0) + 1
        out[b] = d
    return out


def deployed_clip(shaped, bot):
    """Median notional actually put at risk — `|pnl_abs/pnl_pct|`.

    NOT the published `caps.clip_usd`: the sizing stack (`brain_clip` x
    drawdown scale x `allocation_scale`) multiplies after the cap is published,
    and pricing a book at its cap understates it by that whole stack (measured:
    🌾 carry declares $80 and deploys $300).
    """
    vals = []
    for q in ((shaped.get(bot) or {}).get("rows") or []):
        raw = q[7]
        a, p = raw.get("pnl_abs"), raw.get("pnl_pct")
        if isinstance(a, (int, float)) and isinstance(p, (int, float)) and p:
            vals.append(abs(a / p))
    return st.median(vals) if vals else None


# -------------------------------------------------------------- venue fetch
def fetch_book(market_id, limit=25, timeout=25):
    url = "%s/api/v1/orderBookOrders?market_id=%d&limit=%d" % (API, market_id, limit)
    with urllib.request.urlopen(url, timeout=timeout) as r:
        d = json.loads(r.read().decode())
    # SORT — REST snapshots come back unsorted and every consumer takes [0] as
    # top-of-book (`venues/lighter_client._rest_book`). Skipping this is the
    # single most likely way to silently price the wrong level.
    bids = sorted(((float(o["price"]), float(o["remaining_base_amount"]))
                   for o in (d.get("bids") or [])), key=lambda x: -x[0])
    asks = sorted(((float(o["price"]), float(o["remaining_base_amount"]))
                   for o in (d.get("asks") or [])), key=lambda x: x[0])
    return {"bids": bids, "asks": asks}


def quoted_spread_bps(book):
    """Top-of-book spread in bps of mid, or None. Same definition the recording
    books use (`lighter_book_douglas_bot.spread_bps`), so the calibration
    compares like with like: a crossed or empty book makes NO claim."""
    bids, asks = (book or {}).get("bids") or [], (book or {}).get("asks") or []
    if not bids or not asks:
        return None
    bid, ask = bids[0][0], asks[0][0]
    mid = (bid + ask) / 2.0
    if mid <= 0 or ask < bid:
        return None
    return (ask - bid) / mid * 1e4


# ------------------------------------------------------------- the cost model
def book_cost(basket, clip, books_by_coin):
    """Trade-weighted round-trip cost for one book, at its own deployed clip.

    Weighted by how often the book actually traded each coin, so a book that
    takes one trade in an illiquid name and two hundred in a liquid one is not
    priced as if it lived in the illiquid one. Coverage is published: a cost
    computed over a third of a book's trades is reported AS a third, never as
    the book's cost.
    """
    if not basket or not clip:
        return {"rt_bps": None, "why": "no basket or no clip"}
    num = den = 0.0
    covered = missing = unfillable = 0
    per = {}
    for coin, n in basket.items():
        bk = books_by_coin.get(coin)
        if bk is None:
            missing += n
            continue
        c = rt_cost_bps(bk, clip)
        if c is None:
            unfillable += n            # a real finding, not a gap: the visible
            continue                   # book cannot fill this book's own clip
        per[coin] = round(c, 2)
        num += c * n
        den += n
        covered += n
    total = sum(basket.values())
    return {
        "rt_bps": round(num / den, 2) if den else None,
        "clip_usd": round(clip, 2),
        "coverage": round(covered / total, 3) if total else None,
        "n_trades": total,
        "n_unfillable_trades": unfillable,
        "n_uncovered_trades": missing,
        "worst_coin": (max(per, key=per.get) if per else None),
        "worst_bps": (max(per.values()) if per else None),
        "median_coin_bps": (round(st.median(list(per.values())), 2) if per else None),
        "per_coin": per,
    }


def recorded_spreads(trades):
    """{bot: {coin: median recorded quoted spread bps}} — the fleet's own record.

    Only two books record it, which is itself the finding: the fleet measures
    its execution on 2 of 16 living books.
    """
    acc = {}
    for r in trades:
        ex = r.get("extra") or {}
        s = ex.get("spread_bps_entry")
        if not isinstance(s, (int, float)):
            continue
        c = edge_audit.base_symbol(r.get("pair"))
        if not c:
            continue
        acc.setdefault(r.get("bot"), {}).setdefault(c, []).append(float(s))
    return {b: {c: st.median(v) for c, v in d.items()} for b, d in acc.items()}


def calibrate(rec, books_by_coin, tol=CALIB_TOL_BPS):
    """(ok, findings) — can this module reproduce what the fleet already recorded?

    Compares, per recording book, the MEDIAN over coins of the fetched quoted
    spread against the median over the same coins of the recorded one.
    Distributional on purpose: the records are historical and the fetch is now.

    Fail-CLOSED. No recording book, no overlapping coin, or no fetched book =>
    REFUSE. "Nothing to disagree with" must never read as "no disagreement" —
    that is the same fail-open hole `edge_audit.calibrate` closes.
    """
    findings = []
    ok = True
    if not rec:
        # Hoisted to a name rather than split inside the list literal: an
        # implicit concatenation between two elements of a collection is the
        # classic missing-comma bug, and CodeQL rightly cannot tell this one
        # from that one. Cheaper to remove the ambiguity than to argue it.
        why = ("no book records spread_bps_entry — nothing to calibrate "
               "against")
        return False, [["(no recorder)", why]]
    for bot, coins in sorted(rec.items()):
        mine, theirs = [], []
        for c, v in coins.items():
            bk = books_by_coin.get(c)
            if bk is None:
                continue
            q = quoted_spread_bps(bk)
            if q is None:
                continue
            mine.append(q)
            theirs.append(v)
        if len(mine) < 3:
            ok = False
            findings.append([bot, "only %d overlapping coins with a live book "
                                  "— cannot calibrate" % len(mine)])
            continue
        dm, dt = st.median(mine), st.median(theirs)
        d = abs(dm - dt)
        row = [bot, "fetched median %.2fbps vs recorded %.2fbps (n=%d coins), "
                    "delta %.2f, tol %.1f" % (dm, dt, len(mine), d, tol)]
        if d > tol:
            ok = False
            row[1] = "MISMATCH: " + row[1]
        findings.append(row)
    return ok, findings


def _f(v, spec="%.2f", dash="—"):
    return dash if v is None else (spec % v)


def render_md(res):
    if res.get("refused"):
        return ("# PER-BOOK COST MODEL — REFUSED\n\nThe fetched books could not "
                "reproduce the spreads the fleet itself recorded, so no cost is "
                "reported.\n\n```\n%s\n```\n"
                % json.dumps(res.get("calibration"), indent=1))
    L = []
    A = L.append
    A("# PER-BOOK EXECUTION COST — %s" % res["generated"][:16].replace("T", " "))
    A("")
    A("_Round trip via `funding_carry_bot.rt_cost_bps` (the fleet's declared one "
      "owner), walking each book at each book's own **deployed** clip. "
      "Calibrated against the spreads 🪁 kelly and 🧘 douglas record on their own "
      "fills — this refuses if it cannot reproduce them._")
    A("")
    A("## The correction this makes to the Phase-2 baseline")
    A("")
    A("The baseline charged every book the fleet-wide **17.49bps** mean and "
      "reported that it flipped 🌾 carry and 🔮 georgia negative. That reading "
      "does not survive two facts:")
    A("")
    A("1. **17.49 is a MEAN over a right-skewed distribution.** Measured on %d "
      "recorded spreads across %d coins: the median full quoted spread runs "
      "**%.1fbps in the thinnest volume band down to %.1fbps in the thickest** "
      "— a %.1fx span, fitting `spread ~ vol^%.3f` (the square-root liquidity "
      "law). One mean charged to every book overcharges the liquid ones and "
      "**undercharges the thin ones**, which is the dangerous direction."
      % (res["fit"]["n"], res["fit"]["n_coins"], res["fit"]["thin_band_bps"],
         res["fit"]["thick_band_bps"],
         res["fit"]["thin_band_bps"] / max(res["fit"]["thick_band_bps"], 1e-9),
         res["fit"]["beta"]))
    A("2. **The books already pay.** Every living book's P&L is already net of "
      "execution by one of two mechanisms (below). Charging the fleet mean on "
      "top is a **double charge**, not a stress. 🌾 carry is the clearest case: "
      "its P&L is literally `accrued - fees`, so the baseline deducted a round "
      "trip it had already deducted.")
    A("")
    A("**So the question worth asking is headroom, not cost.** Every book's "
      "`breakeven_cost_bps` is what it could pay before its edge is gone; "
      "`cost_now` is what it pays. The ratio is the answer.")
    A("")
    A("## Per book")
    A("")
    A("| book | fill basis | deployed clip | cost now (RT bps) | worst coin | "
      "break-even (RT bps) | headroom | coverage | verdict |")
    A("|---|---|---|---|---|---|---|---|---|")
    for bot, r in sorted(res["books"].items(),
                         key=lambda kv: -(kv[1].get("headroom_x") or -9e9)):
        c = r.get("cost") or {}
        A("| `%s` | %s | %s | **%s** | %s | %s | **%s** | %s | %s |"
          % (bot, r["fill_basis"]["basis"], _f(c.get("clip_usd"), "$%.0f"),
             _f(c.get("rt_bps")),
             ("%s %s" % (c.get("worst_coin"), _f(c.get("worst_bps"), "%.0fbps"))
              if c.get("worst_coin") else "—"),
             _f(r.get("breakeven_bps")),
             _f(r.get("headroom_x"), "%.2fx"),
             _f((c.get("coverage") or 0) * 100.0, "%.0f%%"),
             r.get("verdict") or "—"))
    A("")
    A("`headroom` = break-even cost / cost now. **Below 1.0x the book does not "
      "survive its own execution**; 1-2x is thin. A losing book has no edge to "
      "erase, so its break-even is 0.00 and headroom reads `—` — cost is not "
      "what is wrong with it, and pricing it more precisely would not change "
      "that. Coverage is the share of the book's trades "
      "whose coin had a live book to price; a book priced on part of its basket "
      "says so rather than reporting the part as the whole.")
    A("")
    A("## Fill basis — how each book already accounts for cost")
    A("")
    A("| basis | books | what it means |")
    A("|---|---|---|")
    byb = {}
    for bot, r in res["books"].items():
        byb.setdefault(r["fill_basis"]["basis"], []).append(bot)
    meanings = {
        "real_fills": "a REAL-MONEY row — the ledger prices are actual exchange "
                      "fills, so cost was PAID rather than modelled; the "
                      "live-vs-twin execution gap is `impl_shortfall`'s job",
        "book_walked": "fills walk the LIVE order book (`ShadowBroker`), so the "
                       "crossed spread is inside `entry_price`/`exit_price` and "
                       "therefore already inside `pnl_abs`",
        "modelled_flat": "fills taken at mark with a flat per-side constant "
                         "deducted — exact only at the clip it was calibrated "
                         "for, and `fleet_bus` records it as *fiction* at 6.7x that",
        "unknown": "could not be derived — DECLARED, never guessed",
    }
    for b, bots in sorted(byb.items()):
        A("| **%s** | %d — %s | %s |"
          % (b, len(bots), ", ".join("`%s`" % x for x in sorted(bots)),
             meanings.get(b, "")))
    A("")
    A("## Calibration")
    A("")
    for row in res.get("calibration") or []:
        A("- `%s` — %s" % (row[0], row[1]))
    A("")
    A("_Only **%d of %d** living books record the venue's quoted spread on their "
      "own fills. That is the gap behind all of this: the fleet measures its own "
      "execution on an eighth of itself, so every other book's cost has to be "
      "inferred from the venue rather than read from its record (I14 — the "
      "record outranks the proxy, where a record exists)._"
      % (res["n_recorders"], len(res["books"])))
    return "\n".join(L) + "\n"


def _selftest():
    # rt_cost_bps is the IMPORTED owner, not a copy.
    assert rt_cost_bps is _carry.rt_cost_bps
    bk = {"bids": [[100.0, 10.0]], "asks": [[101.0, 10.0]]}
    assert abs(quoted_spread_bps(bk) - (1.0 / 100.5 * 1e4)) < 1e-6
    assert quoted_spread_bps({"bids": [], "asks": []}) is None
    assert quoted_spread_bps({"bids": [[101.0, 1]], "asks": [[100.0, 1]]}) is None  # crossed

    # unmeasured is NULL, and an unfillable clip is counted, never averaged away
    basket = {"A": 10, "B": 5, "C": 1}
    books = {"A": {"bids": [[100.0, 100.0]], "asks": [[100.1, 100.0]]},
             "B": {"bids": [[100.0, 0.001]], "asks": [[100.5, 0.001]]}}
    out = book_cost(basket, 1000.0, books)
    assert out["n_uncovered_trades"] == 1, out          # C had no book
    assert out["n_unfillable_trades"] == 5, out         # B too thin for $1000
    assert out["coverage"] == round(10 / 16, 3), out
    assert out["rt_bps"] is not None and out["rt_bps"] > 0, out
    assert book_cost({}, 100.0, books)["rt_bps"] is None
    assert book_cost(basket, None, books)["rt_bps"] is None

    # calibration fails CLOSED on nothing-to-compare, and on a real mismatch
    ok, f = calibrate({}, books)
    assert ok is False and "nothing to calibrate" in f[0][1], f
    ok, _ = calibrate({"x": {"A": 9.95, "B": 9.95}}, books)      # <3 coins
    assert ok is False
    tight = {c: {"bids": [[100.0, 1e6]], "asks": [[100.1, 1e6]]} for c in "ABC"}
    ok, f = calibrate({"x": {"A": 9.99, "B": 9.99, "C": 9.99}}, tight)
    assert ok is True, f                                  # ~9.995bps, matches
    ok, f = calibrate({"x": {"A": 200.0, "B": 200.0, "C": 200.0}}, tight)
    assert ok is False and "MISMATCH" in f[0][1], f       # 190bps apart

    # fill_basis is DERIVED and degrades to unknown, never to a guess
    fb = fill_basis("perps-funding-carry-lshadow",
                    root=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    assert fb["basis"] in ("book_walked", "modelled_flat"), fb
    assert fill_basis("no-such-row")["basis"] == "unknown"
    # a live row is classified from the PAYLOAD, before any file is opened —
    # so a slot swap cannot make it wrong (the rule fleet_books exists for).
    lv = fill_basis("freqtrade-mum-lighter", root="/nonexistent", venue="lighter_live")
    assert lv["basis"] == "real_fills", lv
    # and venue_context counts as walking the book (the first cut missed 3 books)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for b in ("band-kelly-lshadow", "lighter-perp-sniper-lshadow",
              "perps-funding-spread-lshadow"):
        got = fill_basis(b, root=root)["basis"]
        assert got == "book_walked", (b, got)
    # a WRAPPER resolves through its core rather than reporting unknown
    bz = fill_basis("book-bezos-lshadow", root=root)
    assert bz["basis"] in ("book_walked", "modelled_flat"), bz
    assert bz.get("via"), bz
    print("cost_model selftest OK")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ledger"); ap.add_argument("--feed"); ap.add_argument("--bus")
    ap.add_argument("--obd", help="local orderBookDetails dump (for volumes/ids)")
    ap.add_argument("--out"); ap.add_argument("--md")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        _selftest(); return 0

    res = edge_audit.run(ledger=a.ledger, feed=a.feed, bus=a.bus, mc_draws=100)
    if res.get("refused"):
        sys.stderr.write("edge_audit refused; cost model cannot speak\n")
        return 2
    trades = edge_audit.load_trades(a.ledger)
    shaped = edge_audit.shape(trades)
    living = sorted(res["books"])
    bk = baskets(shaped, living)

    feed_rows = None
    if a.feed:
        with open(a.feed) as fh:
            feed_rows = (json.load(fh) or {}).get("bots")
    with open(a.obd) as fh:
        obd = json.load(fh)["order_book_details"]
    ids = {r["symbol"]: r["market_id"] for r in obd}
    vols = {r["symbol"]: float(r.get("daily_quote_token_volume") or 0) for r in obd}

    want = {}
    for b, d in bk.items():
        for c, n in d.items():
            want[c] = want.get(c, 0) + n
    order = [c for c in sorted(want, key=lambda x: -want[x]) if c in ids][:FETCH_TOP_N]
    books_by_coin = {}
    for c in order:
        try:
            books_by_coin[c] = fetch_book(ids[c])
        except Exception:                                  # noqa: BLE001
            pass                                           # missing, not zero

    rec = recorded_spreads(trades)
    ok, findings = calibrate(rec, books_by_coin)
    if not ok:
        out = {"refused": True, "calibration": findings}
        if a.md:
            with open(a.md, "w") as fh:
                fh.write(render_md(out))
        print(render_md(out))
        return 2

    # the volume/spread fit, reported so the "17.49 is a mean" claim is checkable
    obs = []
    for r in trades:
        s = (r.get("extra") or {}).get("spread_bps_entry")
        c = edge_audit.base_symbol(r.get("pair"))
        v = vols.get(c)
        if isinstance(s, (int, float)) and v:
            obs.append((v / 1e6, float(s)))
    obs.sort()
    third = max(1, len(obs) // 6)
    xs = [math.log10(max(o[0], 1e-3)) for o in obs]
    ys = [math.log10(max(o[1], 1e-3)) for o in obs]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    beta = (sum((p - mx) * (q - my) for p, q in zip(xs, ys))
            / sum((p - mx) ** 2 for p in xs))
    fit = {"n": len(obs), "n_coins": len({edge_audit.base_symbol(r.get("pair"))
                                          for r in trades
                                          if (r.get("extra") or {}).get("spread_bps_entry")}),
           "beta": round(beta, 3),
           "thin_band_bps": round(st.median([o[1] for o in obs[:third]]), 2),
           "thick_band_bps": round(st.median([o[1] for o in obs[-third:]]), 2)}

    books = {}
    for b in living:
        a_ = res["books"][b]
        cost = book_cost(bk.get(b) or {}, deployed_clip(shaped, b), books_by_coin)
        be = a_.get("breakeven_cost_bps")
        rt = cost.get("rt_bps")
        head = (be / rt) if (be and rt) else None
        if not be:
            verdict = "no edge to price"
        elif head is None:
            verdict = "cost unmeasurable"
        elif head < 1.0:
            verdict = "**does not survive its own execution**"
        elif head < 2.0:
            verdict = "thin"
        else:
            verdict = "comfortable"
        _venue = ((next((x for x in (feed_rows or []) if x.get("bot") == b), {})
                   or {}).get("extra") or {}).get("venue")
        books[b] = {"fill_basis": fill_basis(b, root=os.path.dirname(
                        os.path.dirname(os.path.abspath(__file__))),
                        venue=_venue),
                    "cost": cost, "breakeven_bps": be,
                    "headroom_x": round(head, 2) if head else None,
                    "verdict": verdict}
    out = {"generated": _dt.datetime.now(_dt.timezone.utc).isoformat(),
           "refused": False, "calibration": findings, "fit": fit,
           "n_recorders": len(rec), "fetched_coins": len(books_by_coin),
           "books": books}
    if a.out:
        with open(a.out, "w") as fh:
            json.dump(out, fh, default=str, indent=1)
    md = render_md(out)
    if a.md:
        with open(a.md, "w") as fh:
            fh.write(md)
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
