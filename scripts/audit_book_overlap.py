#!/usr/bin/env python3
"""audit_book_overlap.py — ARE OUR BOOKS HOLDING THE SAME COIN?

WHY (2026-08-13 (lz)). The fleet grades every book independently and allocates
capital by each book's own claim, so two books holding the SAME position read
as two independent bets. On this venue that assumption broke quietly: THREE
funding books now enter at the same bar — 🌾 carry, 🎸 Barnesy's carry sleeve
and 🏦 Rich Dad all take ~20% TRUE apr / $2M turnover / crypto-only — while the
venue's ENTIRE crypto population at that bar is four names (KAITO, XMR, PAXG,
XRP), present in ~6.7% of scout snapshots.

Nothing in the fleet could ask the question, for a mundane reason: two of those
books published an open-position COUNT and no coin names. Concentration is a
property of the COIN, so a count cannot express it. `(lz)` added `held` to both;
this reads it.

TWO MODES, because there are two moments the question matters:

  (default) NOW — cross-book overlap in the live payload. Which coins are held
      by more than one book, how much notional sits on each, and what the
      fleet's effective bet count actually is once duplicates collapse.

  --gate APR --floor USD — BEFORE A BOOK IS BORN. Replays the scout's own tape
      and answers: how many coins would a book with THIS gate actually get, how
      often, and WHICH BOOKS ALREADY HOLD THEM. A new book whose supply is
      entirely spoken for is not new edge — it is the same bet at a new row id,
      and the fleet has now done that once (🏦 Rich Dad, born into 🌾's slot).

READ-ONLY. Prints and exits non-zero on a finding; moves no capital, writes no
lever, retires nothing. `--strict` makes overlap itself an error (for CI);
by default only a HARD finding (a coin held by 3+ books) exits non-zero, so
this can run in a pipeline without failing on ordinary two-book overlap.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import defaultdict

# The funding books that share a supply. Membership is RULE-DRIVEN — a book
# belongs here if it enters on a funding rate over the venue's own universe —
# not curated, so a new funding book is a one-line addition rather than a
# silent omission (the census-hole class, (jb)).
FUNDING_BOOKS = [
    "perps-funding-carry-lshadow",       # 🌾 carry
    "band-barnes-lshadow",               # 🎸 Barnesy (carry + xsect sleeves)
    "book-kiyosaki-lshadow",             # 🏦 Rich Dad
    "band-garrett-lshadow",              # 🛢️ Garrett (thin tier — different slice)
    "perps-funding-lighter-lshadow",     # 💸 Farmer shadow
    "perps-funding-lighter-lighter",     # 💸 Farmer LIVE — real money
    "perps-funding-spread-lshadow",      # ⚖️ Counterweight
]
LIVE_BOOKS = {"perps-funding-lighter-lighter"}
CRYPTO_CLASS = 2


def db_url() -> str:
    u = os.environ.get("DATABASE_URL") or os.environ.get("DATABASE_PUBLIC_URL")
    if u:
        return u.strip()
    try:
        out = subprocess.run(
            ["railway", "variables", "--service", "Postgres", "--kv"],
            capture_output=True, text=True, timeout=60).stdout
    except Exception:  # noqa: BLE001
        out = ""
    for line in out.splitlines():
        if line.startswith("DATABASE_PUBLIC_URL="):
            return line.split("=", 1)[1].strip()
    sys.exit("no DATABASE_URL: set it in the env, or `railway login`")


def _extra(v):
    return v if isinstance(v, dict) else (json.loads(v) if v else {})


def holdings(cur):
    """{bot: {coin: side}} plus the books that DON'T say — reported, never
    silently treated as flat. A book that publishes no `held` is invisible to
    this audit, and invisible must never read as empty (I4/(kw))."""
    cur.execute("SELECT bot, open_trades, extra FROM bot_pnl WHERE bot = ANY(%s)",
                (FUNDING_BOOKS,))
    held, silent = {}, []
    for bot, open_n, extra in cur.fetchall():
        e = _extra(extra)
        h = e.get("held")
        if h is None:
            h = e.get("carries")
        if isinstance(h, dict):
            held[bot] = {c: (v if isinstance(v, str) else "?") for c, v in h.items()}
        elif int(open_n or 0) > 0:
            silent.append((bot, int(open_n or 0)))
        else:
            held[bot] = {}
    return held, silent


def living_gates(cur):
    """{bot: {enter_apr, min_vol}} read from each book's OWN published payload.

    Deliberately read rather than hand-listed: a gate copied into this file
    would drift from the running value, which is the exact failure
    `audit_lever_bounds`'s drift arm exists for. Books publish the pair in two
    shapes — top level (💸 Farmer, 🛢️ Garrett) or under `caps` (🌾 carry,
    🎸 Barnesy, 🏦 Rich Dad) — so both are accepted.
    """
    cur.execute("SELECT bot, extra FROM bot_pnl WHERE bot = ANY(%s)", (FUNDING_BOOKS,))
    out = {}
    for bot, extra in cur.fetchall():
        e = _extra(extra)
        caps = e.get("caps") if isinstance(e.get("caps"), dict) else {}
        g = {}
        for key, dest in (("enter_apr", "enter_apr"), ("min_vol", "min_vol"),
                          ("carry_min_vol", "min_vol"), ("max_vol", "max_vol")):
            v = e.get(key, caps.get(key))
            if isinstance(v, (int, float)) and not isinstance(v, bool) \
                    and dest not in g:
                g[dest] = float(v)
        # `max_vol` is legitimately absent on an unbounded book and legitimately
        # null on one that publishes it as "no ceiling" — those are the SAME
        # state and both mean unbounded. What is NOT the same is a book that
        # publishes no volume bound at all: that is UNKNOWN, and the caller
        # must not read it as unbounded (an unpublished ceiling is how 🛢️
        # Garrett's band got counted as a rival for a supply it excludes).
        g["vol_known"] = ("min_vol" in g) or ("max_vol" in g) \
            or ("max_vol" in e) or ("max_vol" in caps)
        if g.get("enter_apr") is not None:
            out[bot] = g
    return out


def admits(g, gate, floor):
    """Does this living book's gate take the proposed supply?

    Returns "yes" / "no" / "unknown". Three-valued ON PURPOSE: a detector that
    collapses unknown into yes overstates and gets ignored ((gl)'s warning
    class), and one that collapses it into no under-reports the very
    concentration this script exists to find.
    """
    if g["enter_apr"] > gate + 1e-9:
        return "no"                      # stricter apr bar — never sees it
    if not g.get("vol_known"):
        return "unknown"
    mn, mx = g.get("min_vol"), g.get("max_vol")
    if mx is not None and floor >= mx:
        return "no"                      # the supply sits ABOVE its band
    if mn is not None and mn > floor + 1.0:
        return "no"                      # its floor is above the supply
    return "yes"


def scout_classes(cur):
    cur.execute("SELECT payload FROM bot_state_history WHERE key='lighter-market' "
                "ORDER BY ts DESC LIMIT 1")
    row = cur.fetchone()
    return (row[0] or {}).get("classes", {}) if row else {}


def report_now(cur) -> int:
    held, silent = holdings(cur)
    print("=" * 78)
    print("CROSS-BOOK OVERLAP — what the funding books are holding RIGHT NOW")
    print("=" * 78)
    for bot in sorted(held):
        names = ", ".join(f"{c}({s})" for c, s in sorted(held[bot].items())) or "—"
        tag = "  [REAL MONEY]" if bot in LIVE_BOOKS else ""
        print(f"  {bot:32s} {len(held[bot]):2d}  {names}{tag}")
    if silent:
        print("\n  !! BOOKS HOLDING POSITIONS THEY DO NOT NAME "
              "(invisible to this audit, NOT flat):")
        for bot, n in silent:
            print(f"     {bot:32s} open={n}, no `held` field")

    by_coin = defaultdict(list)
    for bot, h in held.items():
        for c, s in h.items():
            by_coin[c].append((bot, s))
    dupes = {c: v for c, v in by_coin.items() if len(v) > 1}
    print(f"\n  distinct coins held: {len(by_coin)}   "
          f"positions: {sum(len(h) for h in held.values())}")
    hard = 0
    if dupes:
        print("\n  COINS HELD BY MORE THAN ONE BOOK:")
        for c, v in sorted(dupes.items(), key=lambda kv: -len(kv[1])):
            sides = {s for _b, s in v}
            note = ("  <- SAME SIDE, concentration" if len(sides) == 1
                    else "  (opposing sides — the books partly net out)")
            flag = "  ** REAL MONEY IN THE STACK **" if any(
                b in LIVE_BOOKS for b, _s in v) else ""
            print(f"    {c:10s} x{len(v)}  " +
                  ", ".join(f"{b.split('-lshadow')[0]}({s})" for b, s in v) +
                  note + flag)
            if len(v) >= 3:
                hard += 1
    else:
        print("\n  no coin is held by two books right now.")

    # effective bet count: positions collapse to distinct (coin, side)
    slots = {(c, s) for h in held.values() for c, s in h.items()}
    total = sum(len(h) for h in held.values())
    if total:
        print(f"\n  EFFECTIVE BETS: {len(slots)} distinct (coin, side) across "
              f"{total} positions"
              f"  -> {100.0 * (1 - len(slots) / total):.0f}% of positions are duplicates")
        print("  NOTE: `fleet_allocation` ranks each book's claim independently, "
              "so duplicated\n        positions are counted as independent evidence. "
              "This number is the correction.")
    if hard:
        print(f"\n  FINDING: {hard} coin(s) held by THREE OR MORE books.")
    return hard


def report_supply(cur, gate: float, floor: float, persist_h: float,
                  crypto_only: bool) -> int:
    """What supply would a book with this gate actually get — and who already
    holds it? Run this BEFORE minting a funding book."""
    cur.execute("SELECT ts, payload FROM bot_state_history "
                "WHERE key='lighter-market' ORDER BY ts")
    rows = cur.fetchall()
    classes = (rows[-1][1] or {}).get("classes", {}) if rows else {}

    def is_crypto(c):
        try:
            return int(classes.get(c)) == CRYPTO_CLASS
        except (TypeError, ValueError):
            return False

    hot_since, snaps_with, coins, best = {}, 0, defaultdict(int), 0
    for ts, p in rows:
        t = ts.timestamp()
        f, v = p.get("funding") or {}, p.get("vols") or {}
        q = []
        for c, apr_pct in f.items():
            try:
                apr = abs(float(apr_pct)) / 100.0
            except (TypeError, ValueError):
                hot_since.pop(c, None)
                continue
            if apr >= gate:
                hot_since.setdefault(c, t)
            else:
                hot_since.pop(c, None)
                continue
            try:
                vol = float(v.get(c)) * 1e6
            except (TypeError, ValueError):
                continue
            if vol < floor or (t - hot_since[c]) < persist_h * 3600.0:
                continue
            if crypto_only and not is_crypto(c):
                continue
            q.append(c)
        if q:
            snaps_with += 1
            best = max(best, len(q))
            for c in q:
                coins[c] += 1
    n = len(rows) or 1
    days = (rows[-1][0] - rows[0][0]).total_seconds() / 86400.0 if rows else 0
    print("=" * 78)
    print(f"SUPPLY AT gate={gate:.0%} TRUE  floor=${floor/1e6:.1f}M  "
          f"persist={persist_h:g}h  crypto_only={crypto_only}")
    print("=" * 78)
    print(f"  tape: {n} scout snapshots over {days:.1f} days")
    print(f"  snapshots offering >=1 candidate: {snaps_with} ({100.0*snaps_with/n:.2f}%)")
    print(f"  max simultaneous candidates: {best}")
    print(f"  distinct coins over the window: {len(coins)}")
    for c, k in sorted(coins.items(), key=lambda kv: -kv[1])[:12]:
        print(f"     {c:12s} offered in {k:5d} snapshots  class={classes.get(c)}")
    if not coins:
        print("\n  VERDICT: this gate has NO supply on this venue. A book built "
              "here cannot trade.")
        return 1

    # ---- capacity vs supply ------------------------------------------------
    # A supply that cannot fill ONE book's cap cannot support two books, and
    # this is the fact a per-book census can never show: each book reports
    # "0 eligible" and reads as merely quiet.
    print(f"\n  CAPACITY vs SUPPLY: at most {best} coin(s) qualify at once.")

    # ---- gate collision ----------------------------------------------------
    # The decision input, and NOT the same question as "who holds it now": the
    # books may all be flat this minute and still be three claimants on one
    # supply. A gate ADMITS this supply when its bar is no stricter than the
    # proposed one — i.e. it would take the same coins whenever they appear.
    gates = living_gates(cur)
    buckets = defaultdict(list)
    for b, g in gates.items():
        buckets[admits(g, gate, floor)].append((b, g))
    rivals = buckets["yes"]

    def _line(b, g):
        mn, mx = g.get("min_vol"), g.get("max_vol")
        band = ""
        if mn is not None or mx is not None:
            band = (f"  vol=[{(mn or 0)/1e6:.2f}M,"
                    f"{'inf' if mx is None else f'{mx/1e6:.2f}M'})")
        return (f"     {b:32s} enter_apr={g['enter_apr']:.3g}{band}"
                + ("   [REAL MONEY]" if b in LIVE_BOOKS else ""))

    print()
    if rivals:
        print("  LIVING BOOKS WHOSE GATE ALREADY ADMITS THIS SUPPLY:")
        for b, g in sorted(rivals):
            print(_line(b, g))
    else:
        print("  no living book's gate admits this supply.")
    if buckets["no"]:
        print("\n  books EXCLUDED by their own band or bar (not rivals):")
        for b, g in sorted(buckets["no"]):
            print(_line(b, g))
    if buckets["unknown"]:
        print("\n  !! books whose VOLUME BOUND IS UNPUBLISHED — cannot be ruled "
              "in or out:")
        for b, g in sorted(buckets["unknown"]):
            print(_line(b, g))
        print("     (these are NOT counted as rivals below — an unpublished "
              "ceiling must not\n      manufacture a finding. Publish "
              "`min_vol`/`max_vol` on them to close the gap.)")

    held, _silent = holdings(cur)
    already = {c: [b for b, h in held.items() if c in h] for c in coins}
    taken = {c: v for c, v in already.items() if v}
    if taken:
        print("\n  ...and these coins are held RIGHT NOW:")
        for c, bots in sorted(taken.items()):
            print(f"     {c:12s} <- " + ", ".join(b.split("-lshadow")[0] for b in bots))

    print()
    if len(rivals) >= 2:
        print(f"  VERDICT: {len(rivals)} living books already claim this supply, and it "
              f"is {len(coins)} coin(s) deep.\n           A book minted here is largely "
              "the SAME BET at a new row id — not new\n           edge. Differentiate "
              "the gate (a different apr band or volume tier),\n           or do not "
              "mint it.")
        return 1
    if taken and len(taken) / len(coins) >= 0.5:
        print("  VERDICT: most of this supply is already held. Differentiate or "
              "do not mint.")
        return 1
    print("  VERDICT: supply exists and is not already spoken for.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gate", type=float,
                    help="TRUE apr entry bar of a PROPOSED book, e.g. 0.20")
    ap.add_argument("--floor", type=float, default=2e6,
                    help="24h $ turnover floor of the proposed book (default 2e6)")
    ap.add_argument("--persist-h", type=float, default=6.0)
    ap.add_argument("--allow-noncrypto", action="store_true")
    ap.add_argument("--strict", action="store_true",
                    help="exit non-zero on ANY two-book overlap, not just 3+")
    args = ap.parse_args()

    import psycopg2
    conn = psycopg2.connect(db_url())
    cur = conn.cursor()
    try:
        if args.gate is not None:
            return report_supply(cur, args.gate, args.floor, args.persist_h,
                                 not args.allow_noncrypto)
        hard = report_now(cur)
        if args.strict:
            held, _s = holdings(cur)
            by = defaultdict(int)
            for h in held.values():
                for c in h:
                    by[c] += 1
            return 1 if any(v > 1 for v in by.values()) else 0
        return 1 if hard else 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
