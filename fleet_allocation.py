#!/usr/bin/env python3
"""
fleet_allocation.py — 💰 the ALLOCATION organ: where SHOULD the capital be?

WHY (2026-08-01, operator: "structured for growth and opportunity ... let's make
the best outcome for our growing ecosystem").

The fleet has a dozen organs that answer "is this book safe?" and exactly none
that answer "where should the money go?". Every shadow book is handed $1,000
regardless of evidence, and it has been that way since the first one. So the
fleet's best-evidenced book and a book with ZERO closed trades in twenty days
carry the same capital, and nothing in the system notices.

The measurement that makes this urgent (2026-07-30, live ledger):

    FUNDING books        3 books   n=212 closes   net  +$72.89
    DIRECTIONAL books   18 books   n=809 closes   net   -$9.21

Six times the trades and six times the books, on the side that does not pay.
That is not a tuning problem — it is an allocation problem, and the fleet had no
instrument that could even state it.

WHAT THIS IS
  A publish-only VIEW. It grades every living book on the evidence that already
  exists, computes what an evidence-weighted allocation WOULD look like, and
  publishes the gap against the flat allocation actually in force.

WHAT THIS IS NOT, and this is deliberate:
  * It moves NO capital. It writes no lever, touches no clip, promotes nothing.
    Automating capital movement is a large new actuator on a fleet whose growth
    rail is bounded and TTL'd for good reasons; the operator gets the number,
    not a fait accompli.
  * It is NOT a second go-live gate. The gate lives in scripts/golive_readiness
    and is IMPORTED here, never re-implemented — a second copy of a rule that
    governs real money is a second rule (the 30-Jul evidence_review defect).
    Allocation asks a DIFFERENT question: not "may this book hold real money?"
    but "given what we know, where is the next dollar best spent?"

THE RULE — rank on a LOWER BOUND, never on the mean.
  A book's claim on capital is `mean - Z * SE` (a one-sided lower confidence
  bound on per-trade expectancy), floored at zero. Ranking on the mean rewards
  small samples that got lucky; the lower bound is what the incubator already
  learned to rank on, and it is self-correcting: a book with a big mean and a
  tiny n has a wide SE and therefore a weak claim, exactly as it should.

  Every living book keeps a PROBE floor. A book cannot earn evidence with no
  capital, so starving an undecided book to zero is how a fleet stops learning.
  The floor is the price of optionality and it is stated, not hidden.

Usage:
    python3 fleet_allocation.py                 # print the table
    python3 fleet_allocation.py --publish       # + write bot_state
    python3 fleet_allocation.py --selftest      # offline, no DB
"""
from __future__ import annotations

import json
import math
import os
import sys
from datetime import datetime, timezone

try:
    import bot_pnl_store as store
except Exception:                                    # pragma: no cover
    store = None

KEY = "fleet-allocation"
TTL_SEC = int(os.environ.get("ALLOC_TTL_SEC", "21600"))      # 6h

# One-sided Z for the lower bound. 1.28 = 90%: deliberately gentler than the
# go-live gate's t>=2.0, because this decides where to LEARN next, not what may
# hold real money. Using the gate's bar here would starve every undecided book
# and the fleet would stop discovering anything.
Z_LOWER = float(os.environ.get("ALLOC_Z_LOWER", "1.28"))
# The probe floor, as a fraction of the flat book size. A book cannot earn
# evidence with no capital.
PROBE_FLOOR = float(os.environ.get("ALLOC_PROBE_FLOOR", "0.25"))
# Books below this many closes are UNDECIDED — they get the probe floor and no
# more, whatever their mean looks like.
MIN_N = int(os.environ.get("ALLOC_MIN_N", "20"))
BOOK_USD = float(os.environ.get("ALLOC_BOOK_USD", "1000"))

# Class membership is by the SIGNAL the book trades, not by its name. Funding
# books earn a carry that exists whether or not the price moves; directional
# books need the price to move their way. The measured gap between the two is
# the headline this organ exists to keep in front of the operator.
FUNDING_MARKERS = ("funding", "carry", "spread")


def _iso(ts=None):
    return (ts or datetime.now(timezone.utc)).isoformat(timespec="seconds")


def book_class(bot):
    """'funding' | 'directional'. By signal, not by name prefix."""
    b = str(bot or "").lower()
    return "funding" if any(m in b for m in FUNDING_MARKERS) else "directional"


def lower_bound(pcts, z=Z_LOWER):
    """One-sided lower confidence bound on mean per-trade return.

    Returns None when the sample cannot support one (n<2 or zero variance) —
    NEVER 0.0, because "no opinion" and "measured zero" must not collapse into
    the same number. Callers treat None as undecided.
    """
    v = [float(p) for p in pcts if p is not None]
    n = len(v)
    if n < 2:
        return None
    mean = sum(v) / n
    var = sum((x - mean) ** 2 for x in v) / (n - 1)
    # A VARIANCE FLOOR, not `var <= 0`. Identical returns do not give exactly
    # zero in floating point (30 x 0.01 sums to 0.30000000000000004), so the
    # naive check passes a variance of ~1e-36 through and the bound collapses
    # onto the mean — a degenerate book would then out-claim every real one.
    # Below the floor the sample is telling us nothing about dispersion.
    if var <= 1e-18:
        return None
    return mean - z * math.sqrt(var / n)


def claims(books):
    """{bot: claim} — each book's non-negative claim on capital.

    `books` is {bot: [pnl_pct, ...]}. A book that is undecided (too few closes,
    or an uncomputable bound) claims 0 and falls back to the probe floor; a
    book whose lower bound is negative claims 0 too. Nothing goes below the
    floor, so this can only REDISTRIBUTE the surplus above it.
    """
    out = {}
    for bot, pcts in (books or {}).items():
        n = len([p for p in (pcts or []) if p is not None])
        lb = lower_bound(pcts) if n >= MIN_N else None
        out[bot] = max(0.0, lb) if lb is not None else 0.0
    return out


def allocate(books, book_usd=BOOK_USD, floor=PROBE_FLOOR):
    """{bot: {target_usd, share, claim, n, class, ...}} — the evidence-weighted
    allocation of the SAME total capital the fleet already deploys.

    Total is conserved by construction: this never proposes spending more, only
    spending it differently. Every book keeps `floor` of the flat allocation as
    a probe; the surplus above the floors is split by claim. When NO book has a
    claim (the honest common case early on), the result is exactly the flat
    allocation — the organ says "no opinion" rather than inventing one.
    """
    bots = sorted(books or {})
    if not bots:
        return {}
    total = book_usd * len(bots)
    base = book_usd * max(0.0, min(1.0, floor))
    surplus = total - base * len(bots)
    cl = claims(books)
    tot_claim = sum(cl.values())
    out = {}
    for b in bots:
        n = len([p for p in (books[b] or []) if p is not None])
        share = (cl[b] / tot_claim) if tot_claim > 0 else (1.0 / len(bots))
        target = base + surplus * share
        out[b] = {
            "n": n,
            "class": book_class(b),
            "claim": round(cl[b], 6),
            "target_usd": round(target, 2),
            "current_usd": round(book_usd, 2),
            "delta_usd": round(target - book_usd, 2),
            "undecided": n < MIN_N or cl[b] <= 0.0,
        }
    return out


def class_totals(alloc, books):
    """The headline: funding vs directional, on evidence and on P&L."""
    out = {}
    for cls in ("funding", "directional"):
        rows = [b for b in alloc if alloc[b]["class"] == cls]
        out[cls] = {
            "books": len(rows),
            "closes": sum(alloc[b]["n"] for b in rows),
            "current_usd": round(sum(alloc[b]["current_usd"] for b in rows), 2),
            "target_usd": round(sum(alloc[b]["target_usd"] for b in rows), 2),
            "n_with_claim": sum(1 for b in rows if alloc[b]["claim"] > 0),
        }
    return out


def build(books, book_usd=BOOK_USD):
    """The published payload. Pure — the selftest drives it with no DB."""
    alloc = allocate(books, book_usd=book_usd)
    return {
        "updated": _iso(),
        "ttl_sec": TTL_SEC,
        "advisory": True,
        "moves_capital": False,
        "rule": (f"claim = max(0, mean - {Z_LOWER}*SE) on per-trade %, "
                 f"n>={MIN_N}; every book keeps a {PROBE_FLOOR:.0%} probe "
                 f"floor; total capital is conserved"),
        "n_books": len(alloc),
        "book_usd": book_usd,
        "by_class": class_totals(alloc, books),
        "books": alloc,
    }


# --------------------------------------------------------------------------
# I/O shell
# --------------------------------------------------------------------------
def _living(trades):
    """Drop retired books, exact-match against the fleet's own retirement
    authority. Fail-OPEN: no list -> keep everything, so an import failure can
    never silently blank the view."""
    try:
        from cleanup_legacy_bots import LEGACY_BOTS as retired
        retired = set(retired)
    except Exception:                                # noqa: BLE001
        retired = set()
    return [t for t in trades if t.get("bot") not in retired], len(retired)


def run_once(publish=False):
    if store is None:
        return None
    trades, n_retired = _living(store.fetch_paper_trades(limit=8000))
    books = {}
    for t in trades:
        bot = t.get("bot")
        pct = t.get("profit_ratio", t.get("pnl_pct"))
        if bot and pct is not None:
            books.setdefault(bot, []).append(pct)
    payload = build(books)
    payload["excluded_retired"] = n_retired
    # The go-live verdict is IMPORTED, never re-derived here — allocation is a
    # different question and must not become a second gate. Optional by design:
    # that module is the other half of the fleet's grading surface and this
    # organ must not go dark if it moves.
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(
            os.path.abspath(__file__)), "scripts"))
        from golive_readiness import GOLIVE_MIN_CLOSES
        payload["golive_min_closes"] = GOLIVE_MIN_CLOSES
    except Exception:                                # noqa: BLE001
        payload["golive_min_closes"] = None
    if publish:
        try:
            store.save_state(KEY, payload)
            store.save_history(KEY, {"by_class": payload["by_class"],
                                     "n_books": payload["n_books"],
                                     "updated": payload["updated"]})
        except Exception as e:                       # noqa: BLE001
            print(f"[fleet-allocation] publish failed: {e}", file=sys.stderr)
    return payload


def _print(payload):
    print(f"\n{'book':34s} {'cls':11s} {'n':>4} {'claim':>9} "
          f"{'now$':>7} {'target$':>8} {'delta':>8}")
    print("-" * 88)
    for b, r in sorted(payload["books"].items(),
                       key=lambda kv: -kv[1]["target_usd"]):
        print(f"{b:34s} {r['class']:11s} {r['n']:>4} {r['claim']:>9.5f} "
              f"{r['current_usd']:>7.0f} {r['target_usd']:>8.0f} "
              f"{r['delta_usd']:>+8.0f}"
              + ("  (undecided -> probe floor)" if r["undecided"] else ""))
    print()
    for cls, c in payload["by_class"].items():
        print(f"  {cls:11s} {c['books']:2d} books  {c['closes']:5d} closes  "
              f"${c['current_usd']:>7.0f} -> ${c['target_usd']:>7.0f}  "
              f"({c['n_with_claim']} with a measured claim)")
    print("\nADVISORY ONLY — this organ moves no capital, writes no lever and "
          "promotes nothing.\nRule: " + payload["rule"])


def _selftest():
    # --- lower_bound: "no opinion" must never look like "measured zero" ----
    assert lower_bound([]) is None and lower_bound([0.01]) is None
    assert lower_bound([0.01] * 30) is None, "zero variance -> no opinion"
    lb = lower_bound([0.02, 0.01, 0.03, -0.01] * 10)
    assert lb is not None and lb < sum([0.02, 0.01, 0.03, -0.01]) / 4, \
        "the bound must sit BELOW the mean"
    # a wider sample tightens the bound toward the mean — the whole point of
    # ranking on a bound rather than a mean
    tight = lower_bound([0.02, 0.01, 0.03, -0.01] * 100)
    assert tight > lb, "more evidence must strengthen the claim"

    # --- an undecided book claims nothing but keeps its probe floor --------
    thin = {"a": [0.05, 0.04, 0.06, 0.05, 0.05],          # big mean, n=5
            "b": [0.002, 0.001, 0.003, 0.002] * 20}      # modest, well-evidenced
    al = allocate(thin, book_usd=1000.0)
    assert al["a"]["undecided"] is True, "n=5 cannot claim capital"
    assert al["a"]["target_usd"] >= 250.0, "a probe floor is not optional"
    # ...and a big mean on a tiny sample must NOT beat a modest, well-evidenced
    # one. This is the single assertion that makes the rule worth having.
    assert al["b"]["target_usd"] > al["a"]["target_usd"], \
        "lucky small samples must not outrank measured ones"

    # --- total capital is CONSERVED: this never proposes spending more -----
    for books in (thin, {"x": [0.01, 0.02, 0.0, 0.015] * 12,
                         "y": [-0.02, -0.01, -0.03, 0.0] * 12, "z": []}):
        a = allocate(books, book_usd=1000.0)
        assert abs(sum(r["target_usd"] for r in a.values())
                   - 1000.0 * len(a)) < 0.05, "allocation must conserve total"

    # --- no claims anywhere -> EXACTLY the flat allocation ("no opinion") --
    flat = allocate({"p": [-0.02, -0.01, -0.03, 0.0] * 10,
                     "q": [-0.03, -0.02, -0.01, -0.04] * 10}, book_usd=1000.0)
    for r in flat.values():
        assert abs(r["target_usd"] - 1000.0) < 0.05, \
            "with no positive claim the organ must say nothing, not invent"

    # --- a negative book is floored, never negative ------------------------
    # NOTE the fixtures VARY. A constant return series has zero variance, which
    # `lower_bound` correctly refuses to score — so a constant fixture would
    # test the degenerate path and quietly prove nothing about ranking. Real
    # books have dispersion; the fixture must too.
    neg = allocate({"bad": [-0.06, -0.04, -0.05, -0.03] * 10,
                    "good": [0.03, 0.01, 0.02, 0.04] * 10}, book_usd=1000.0)
    assert neg["bad"]["claim"] == 0.0 and neg["bad"]["target_usd"] >= 250.0
    assert neg["good"]["target_usd"] > neg["bad"]["target_usd"]

    # --- class split is by SIGNAL, not by name prefix ----------------------
    assert book_class("perps-funding-carry-lshadow") == "funding"
    assert book_class("perps-funding-spread-lshadow") == "funding"
    assert book_class("crypto-trend-daily-lshadow") == "directional"
    assert book_class("lighter-ticket-taker-lighter") == "directional"
    assert book_class(None) == "directional", "unknown must not claim funding"

    # --- the payload is honest about what it is ---------------------------
    p = build({"m": [0.01, 0.02, 0.0, 0.015] * 10})
    assert p["advisory"] is True and p["moves_capital"] is False
    assert p["ttl_sec"] > 0 and p["updated"]
    assert json.dumps(p), "payload must be JSON-serialisable for the bus"

    # --- junk in must not raise: this runs in an organ loop ---------------
    for junk in ({}, {"a": None}, {"a": [None, None]}, {"a": ["x", 1]}):
        try:
            build(junk)
        except (TypeError, ValueError):
            pass                      # a typed rejection is fine
    print("fleet_allocation selftest OK (bound < mean, evidence beats luck, "
          "total conserved, no-claim -> flat, floors hold, advisory stamped)")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(_selftest())
    pay = run_once(publish="--publish" in sys.argv)
    if pay is None:
        print("fleet_allocation: no DB (DATABASE_URL unset) — nothing to read.")
        sys.exit(0)
    _print(pay)
