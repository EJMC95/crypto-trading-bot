#!/usr/bin/env python3
"""review_disloc_census.py — the census review Snap Back's alerts keep asking for.

Reads the dislocation census (per-coin count / max_bps / last seen of every
>=50bps Lighter-vs-HL print) and answers the promotion question: how DENSE is
the tradeable (>=150bps entry-grade) opportunity, and where does it live?

Sources, in order:
  1. DATABASE_URL set -> bot_state directly (runs in any fleet container).
  2. Else the dashboard's public /disloc.json endpoint.

Read-only. Verdict rules of thumb printed at the end mirror the bot's charter:
shadow record >= 20-30 round-trips before any clip-size/go-live discussion.
"""
import json
import os
import sys
import urllib.request

DISLOC_URL = os.environ.get(
    "DISLOC_URL",
    "https://pnl-dashboard-production-858c.up.railway.app/disloc.json")
ENTER_BPS = 150.0   # the bot's tradeable gate (DISLOC_ENTER_BPS default)


def load_books():
    if os.environ.get("DATABASE_URL"):
        try:
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            import bot_pnl_store as store
            books = {}
            for key in ("lighter-dislocation-lshadow", "lighter-dislocation-lighter",
                        "lighter-dislocation"):
                st = store.load_state(key)
                if st and st.get("census"):
                    books[key] = {"census": st["census"], "updated_at": None}
            if books:
                return books
        except Exception as e:
            print(f"(direct DB read failed: {e} — falling back to {DISLOC_URL})")
    with urllib.request.urlopen(DISLOC_URL, timeout=20) as r:
        d = json.loads(r.read().decode())
    if "error" in d:
        raise SystemExit(f"endpoint says: {d['error']} "
                         "(dashboard not redeployed with /disloc.json yet?)")
    return d["books"]


def main():
    books = load_books()
    for book, blob in books.items():
        census = blob.get("census") or {}
        if not census:
            continue
        total = sum(int(c.get("count") or 0) for c in census.values())
        print(f"\n== {book} — {total} census events (>=50bps) ==")
        print(f"{'coin':8} {'events':>6} {'entry?':>7} {'max_bps':>8} {'enter_n':>8}  last_seen")
        rows = sorted(census.items(), key=lambda kv: -int(kv[1].get("count") or 0))
        n_entry_coins = 0
        for coin, c in rows:
            mx = float(c.get("max_bps") or 0)
            entry = mx >= ENTER_BPS
            n_entry_coins += 1 if entry else 0
            enter_n = c.get("count_enter", "-")   # populated once the gate0
            # census records entry-grade events separately; '-' = older blob
            print(f"{coin:8} {int(c.get('count') or 0):6} {('YES' if entry else 'no'):>7} "
                  f"{mx:8.1f} {str(enter_n):>8}  {str(c.get('last_iso') or '')[:16]}")
        print(f"\ncoins with an entry-grade (>= {ENTER_BPS:.0f}bps) print: "
              f"{n_entry_coins}/{len(rows)}")
        print("verdict guide: the census proves dislocations EXIST; promotion "
              "needs DENSITY (entry-grade events/week via count_enter) and a "
              "shadow record of >=20-30 round-trips — one winner is not a record.")


if __name__ == "__main__":
    main()
