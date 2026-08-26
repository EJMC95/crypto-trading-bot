#!/usr/bin/env python3
"""Does `fleet_bus.NONCRYPTO_BASES` still match the venue?  [2026-08-20 (tt)]

WHY THIS EXISTS. `fleet_bus.is_crypto` answers in three tiers: an explicit
override, the scout's published `classes` (the venue's own `strategy_index`),
and — when the scout is dark or stale — the hand-maintained `NONCRYPTO_BASES`
fallback. That third tier is not decoration: its whole job is that *"an organ
outage must not silently re-admit 41 equities to a funding-rank book"*.

It drifts by construction. The list is reconciled by hand; the venue lists new
instruments weekly. Measured on the day this shipped: **8 of 101 active
non-crypto books were missing** (AXTI, CASHCAT, KIOXIA, KORU, MRNA, SOXS,
US10Y, WDC — all recent listings), so with a dark scout every crypto-screened
book in the fleet failed OPEN on those eight. `(ki)` measured the same class of
drift at 41 of 204 a fortnight earlier. Nothing was watching between.

WHAT IT CANNOT BE. This check needs the venue's live `strategy_index`, so it
cannot run in CI without network — and a guard that silently no-ops offline is
worse than none ((po): a check that inspects nothing reports clean). So it
FAILS LOUDLY when it cannot reach the venue rather than passing, and it is
registered as a GUARD-ONLY audit whose `--selftest` (pure, offline) pins the
comparison logic itself.

  python3 scripts/audit_noncrypto_fallback.py            # live check
  python3 scripts/audit_noncrypto_fallback.py --selftest # offline logic pin
"""
import argparse
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OBD = "https://mainnet.zklighter.elliot.ai/api/v1/orderBookDetails"
CRYPTO_IDX = 2


def drift(rows, fallback, override):
    """(missing, stale) — venue-noncrypto absent from the fallback, and
    fallback names the venue now calls CRYPTO.

    `override` names are the fleet's DELIBERATE disagreements with the venue
    (PAXG), so they are excluded from both directions rather than reported as
    drift — an override is a judgement call, not a mistake.
    """
    active = [r for r in rows
              if str(r.get("status") or "active").lower() == "active"]
    venue = {}
    for r in active:
        sym = str(r.get("symbol") or "").strip().upper()
        try:
            venue[sym] = int(r.get("strategy_index"))
        except (TypeError, ValueError):
            continue
    missing = sorted(s for s, c in venue.items()
                     if c != CRYPTO_IDX and s not in fallback
                     and s not in override)
    stale = sorted(s for s in fallback
                   if venue.get(s) == CRYPTO_IDX and s not in override)
    return missing, stale, venue


def _selftest():
    rows = [
        {"symbol": "BTC", "status": "active", "strategy_index": 2},
        {"symbol": "SPY", "status": "active", "strategy_index": 5},
        {"symbol": "NEWEQ", "status": "active", "strategy_index": 5},
        {"symbol": "PAXG", "status": "active", "strategy_index": 2},
        {"symbol": "WASCRYPTO", "status": "active", "strategy_index": 2},
        {"symbol": "DEADEQ", "status": "inactive", "strategy_index": 5},
        {"symbol": "JUNK", "status": "active", "strategy_index": None},
    ]
    fb = {"SPY", "PAXG", "WASCRYPTO"}
    ov = {"PAXG"}
    missing, stale, venue = drift(rows, fb, ov)
    # NEWEQ is non-crypto and absent -> drift. DEADEQ is inactive -> ignored.
    assert missing == ["NEWEQ"], missing
    # WASCRYPTO sits in the fallback but the venue calls it crypto -> stale.
    assert stale == ["WASCRYPTO"], stale
    # the override is reported in NEITHER direction, both ways round
    assert "PAXG" not in missing and "PAXG" not in stale
    # an unparseable class is skipped, never coerced
    assert "JUNK" not in venue
    # a clean list reports nothing
    m2, s2, _ = drift(rows, {"SPY", "NEWEQ", "PAXG"}, ov)
    assert m2 == [] and s2 == [], (m2, s2)
    print("audit_noncrypto_fallback selftest: OK (5 assertions)")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--json", help="read venue rows from a file instead of the network")
    a = ap.parse_args()
    if a.selftest:
        return _selftest()

    import fleet_bus as fb
    if a.json:
        with open(a.json) as fh:
            rows = json.load(fh)
    else:
        try:
            d = json.loads(urllib.request.urlopen(OBD, timeout=45).read())
        except Exception as e:                                  # noqa: BLE001
            # FAIL, never pass: an unreachable venue means this guard inspected
            # nothing, and "clean" would then read as evidence.
            print(f"FAIL: cannot reach the venue ({e}). This guard inspects "
                  f"nothing offline and refuses to report clean.")
            return 2
        rows = d.get("order_book_details") or d.get("orderBookDetails") or []
    if not rows:
        print("FAIL: venue returned no books — refusing to report clean.")
        return 2

    missing, stale, venue = drift(rows, fb.NONCRYPTO_BASES, fb.NONCRYPTO_OVERRIDE)
    n_nc = sum(1 for s, c in venue.items() if c != CRYPTO_IDX)
    print(f"venue: {len(venue)} classified books, {n_nc} non-crypto")
    print(f"fallback NONCRYPTO_BASES: {len(fb.NONCRYPTO_BASES)}  "
          f"override: {sorted(fb.NONCRYPTO_OVERRIDE)}")
    if missing:
        print(f"\nDRIFT — {len(missing)} venue-noncrypto book(s) NOT in the "
              f"fallback. With a dark scout every crypto-screened book in the "
              f"fleet fails OPEN on these:")
        for s in missing:
            print(f"  {s:12s} strategy_index={venue[s]}")
    if stale:
        print(f"\nSTALE — {len(stale)} fallback name(s) the venue now calls "
              f"CRYPTO (a dark scout would wrongly REFUSE these):")
        for s in stale:
            print(f"  {s}")
    if not missing and not stale:
        print("\nOK: the fallback matches the venue.")
        return 0
    print("\nFIX: add/remove the names above in `fleet_bus.NONCRYPTO_BASES`, "
          "grouped by the venue's class, and say in the changelog what moved.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
