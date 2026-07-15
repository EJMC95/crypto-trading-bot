#!/usr/bin/env python3
"""
lighter_market_scout.py — 🛰️ Lighter Scout: the fleet-wide Lighter market map.

WHAT / WHY (2026-07-14, user ask: "an additional lighter scanner that spans
wider options ... so the other bots can be headed toward a net positive
direction")
  Gap Scout's Lighter leg watches six books. This scout watches ALL of them
  (215 markets, two keyless calls) and publishes the venue-wide signals the
  per-bot code can't see, to bot_state `lighter-market` (+ append-only
  history) for the brain, the bus, and any future entry filter to consume:

    stress             median / p90 / max |mark-vs-index premium| (bps) across
                       every liquid book — the venue-wide stress gauge
    prem_outliers      the liquid books trading furthest from fair value
                       (taker entries there pay the premium; it mean-reverts)
    funding_extremes   top |Lighter-native APR| on LIQUID books only — fixes
                       the old bus signal's flaw (max over tiny dead coins)
    funding_divergence Lighter APR vs the median of binance/bybit/hyperliquid
                       for the same symbol — a venue-carry dislocation lead
                       (the funding-veto A/B measures the trailing cost;
                       this is the same force, seen before entry)
    vol_surges         daily quote volume >= 3x the previous snapshot
    oi_moves           open interest moved >= 25% since the previous snapshot
    new_listings /     market set diffs vs the previous snapshot (Perp Sniper
    delisted           TRADES listings; the scout only records the event)

  ADVISORY / PUBLISH-ONLY, per the standing doctrine: nothing trades on these
  keys until a review earns the wiring. Fail-silent end-to-end (Lighter's WAF
  has blocked other REST from Railway; a failed fetch just skips the run) and
  TTL'd so consumers fail safe. Run-once process; run_all.sh loops it.

Usage:
    python3 lighter_market_scout.py            # one scan + publish (if DB)
    python3 lighter_market_scout.py --selftest # offline math checks
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

import bot_pnl_store as store

KEY = "lighter-market"
TTL_SEC = 900
API_BASE = os.environ.get("LIGHTER_API_BASE", "https://mainnet.zklighter.elliot.ai")
MIN_QVOL = float(os.environ.get("SCOUT_MIN_QVOL", "100000"))   # liquid floor $/day
VOL_SURGE_RATIO = float(os.environ.get("SCOUT_VOL_SURGE", "3.0"))
OI_MOVE_FRAC = float(os.environ.get("SCOUT_OI_MOVE", "0.25"))
# Funding-divergence tickets: |Lighter APR - cross-venue median APR| must be
# at least this many percentage points to become a ticket (DATA printed
# +925pp at first light — genuine divergences are triple digits).
DIV_GAP_PP = float(os.environ.get("SCOUT_DIV_GAP", "300"))
TOP_N = 8


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _get(path):
    req = urllib.request.Request(API_BASE + path,
                                 headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


# ---------------------------------------------------------------------------
# PURE COMPUTE (unit-tested offline — no network, no DB)
# ---------------------------------------------------------------------------

def book_stats(books, min_qvol):
    """orderBookDetails rows -> per-symbol dict for ACTIVE books:
    {sym: {prem_bps, qvol, oi, liquid}}. None-safe; junk rows skipped."""
    out = {}
    for b in books:
        try:
            if b.get("status") != "active":
                continue
            sym = b.get("symbol")
            mark = float(b.get("mark_price") or 0.0)
            idx = float(b.get("index_price") or 0.0)
            if not sym or mark <= 0.0 or idx <= 0.0:
                continue
            qvol = float(b.get("daily_quote_token_volume") or 0.0)
            out[sym] = {
                "prem_bps": round((mark / idx - 1.0) * 10_000.0, 1),
                "qvol": qvol,
                "oi": float(b.get("open_interest") or 0.0),
                "liquid": qvol >= min_qvol,
                # coarse intraday shape for the strategy lenses (v1 fields —
                # the bulk endpoint has no candle history)
                "last": float(b.get("last_trade_price") or 0.0),
                "high": float(b.get("daily_price_high") or 0.0),
                "low": float(b.get("daily_price_low") or 0.0),
                "chg": float(b.get("daily_price_change") or 0.0),
            }
        except (TypeError, ValueError):
            continue
    return out


def funding_aprs(rates):
    """funding-rates rows -> ({sym: lighter_apr_pct}, {sym: [other-venue aprs]}).
    Hourly rate -> APR%: rate * 24 * 365 * 100."""
    lighter, others = {}, {}
    for r in rates:
        try:
            sym, rate = r.get("symbol"), r.get("rate")
            if not sym or rate is None:
                continue
            apr = float(rate) * 24 * 365 * 100.0
            if r.get("exchange") == "lighter":
                lighter[sym] = round(apr, 1)
            else:
                others.setdefault(sym, []).append(apr)
        except (TypeError, ValueError):
            continue
    return lighter, others


def _median(xs):
    xs = sorted(xs)
    return xs[len(xs) // 2] if xs else None


def strategy_tickets(stats, lighter_apr, divergence=None):
    """[2026-07-14 user ask] Per-strategy candidate TICKETS — the scanner
    hunting each bot family's setup across the WHOLE venue instead of a fixed
    whitelist. v1 lenses use only today's keyless fields (range position, day
    change, volume, premium, funding); trend-aware lenses come once scout
    history accumulates. ADVISORY + historized: the weekly review grades each
    lens's forward returns BEFORE any bot consumes its feed — a lens only
    earns a consumer by evidence, same doctrine as everything on the bus.

    Lenses -> bot families:
      breakout : Breakout Hunter / Dad   — at the daily high on real volume,
                 not trading rich, longs not paying extreme funding
      dip      : Dip Buyer / Avo Maria   — hard intraday flush to the lows,
                 bounded (avoid falling knives), not rich (v1 has no trend
                 context — tagged so consumers know)
      momentum : Stock Leaders / momo    — strongest liquid day-movers with
                 funding not eating the carry
      divergence: (2026-07-14 addition, nobody in the fleet trades this) —
                 hold the RECEIVING side on Lighter when its funding rate
                 diverges >= DIV_GAP_PP from the cross-venue median for the
                 same symbol: positive gap -> SHORT receives it, negative ->
                 LONG. Skips entries that fight the premium (shorting an
                 already-cheap book / longing a rich one).
    """
    out = {"breakout": [], "dip": [], "momentum": [], "divergence": []}
    for s, v in stats.items():
        if not v["liquid"]:
            continue
        hi, lo, last = v.get("high"), v.get("low"), v.get("last")
        if not hi or not lo or not last or hi <= lo:
            continue
        rng = (last - lo) / (hi - lo)          # 1.0 = at the daily high
        chg = v.get("chg") or 0.0              # venue-reported daily change %
        apr = lighter_apr.get(s)
        rich = v["prem_bps"] > 15.0            # taker longs pay the premium
        longs_pay_hard = apr is not None and apr > 100.0
        row = {"sym": s, "range_pos": round(rng, 2), "chg_pct": round(chg, 2),
               "vol_m": round(v["qvol"] / 1e6, 2), "prem_bps": v["prem_bps"],
               "apr_pct": apr}
        if rng >= 0.9 and chg > 0.0 and not rich and not longs_pay_hard:
            out["breakout"].append(row)
        if rng <= 0.1 and -8.0 <= chg <= -1.0 and not rich:
            out["dip"].append({**row, "trend": "unknown_v1"})
        if chg >= 3.0 and v["qvol"] >= 1e6 and not rich and not longs_pay_hard:
            out["momentum"].append(row)
    for d in divergence or []:
        s = d.get("sym")
        v = stats.get(s) or {}
        gap = d.get("gap_pct") or 0.0
        if abs(gap) < DIV_GAP_PP:
            continue
        side = "short" if gap > 0 else "long"     # receive the divergent rate
        prem = v.get("prem_bps") or 0.0
        if (side == "short" and prem < -15.0) or (side == "long" and prem > 15.0):
            continue                              # don't fight the premium
        out["divergence"].append({"sym": s, "side": side,
                                  "gap_pct": round(gap, 1),
                                  "lighter_apr": d.get("lighter_apr"),
                                  "xvenue_apr": d.get("xvenue_apr"),
                                  "vol_m": round((v.get("qvol") or 0) / 1e6, 2),
                                  "prem_bps": prem})
    out["breakout"].sort(key=lambda r: (-r["range_pos"], -r["vol_m"]))
    out["dip"].sort(key=lambda r: (r["range_pos"], r["chg_pct"]))
    out["momentum"].sort(key=lambda r: -r["chg_pct"])
    out["divergence"].sort(key=lambda r: -abs(r["gap_pct"]))
    return {k: v[:6] for k, v in out.items()}


def build_snapshot(stats, lighter_apr, other_aprs, prev_marks):
    """Assemble the published payload from the pure inputs.
    prev_marks: {sym: [qvol, oi]} from the previous snapshot ({} first run)."""
    liquid = {s: v for s, v in stats.items() if v["liquid"]}
    prems = sorted(abs(v["prem_bps"]) for v in liquid.values())
    stress = None
    if prems:
        stress = {"med": prems[len(prems) // 2],
                  "p90": prems[min(len(prems) - 1, int(0.9 * len(prems)))],
                  "max": prems[-1], "n": len(prems)}

    prem_outliers = [
        {"sym": s, "prem_bps": v["prem_bps"], "vol_m": round(v["qvol"] / 1e6, 2)}
        for s, v in sorted(liquid.items(), key=lambda kv: -abs(kv[1]["prem_bps"]))[:TOP_N]]

    funding_extremes = [
        {"sym": s, "apr_pct": lighter_apr[s], "vol_m": round(liquid[s]["qvol"] / 1e6, 2)}
        for s in sorted((s for s in liquid if s in lighter_apr),
                        key=lambda s: -abs(lighter_apr[s]))[:TOP_N]]

    divergence = []
    for s in liquid:
        if s in lighter_apr and other_aprs.get(s):
            ref = _median(other_aprs[s])
            gap = lighter_apr[s] - ref
            divergence.append({"sym": s, "lighter_apr": lighter_apr[s],
                               "xvenue_apr": round(ref, 1),
                               "gap_pct": round(gap, 1)})
    divergence.sort(key=lambda d: -abs(d["gap_pct"]))

    surges, oi_moves = [], []
    for s, v in liquid.items():
        prev = prev_marks.get(s)
        if not prev:
            continue
        pq, poi = (prev + [0, 0])[:2]
        if pq and v["qvol"] / pq >= VOL_SURGE_RATIO:
            surges.append({"sym": s, "vol_m": round(v["qvol"] / 1e6, 2),
                           "ratio": round(v["qvol"] / pq, 1)})
        if poi and abs(v["oi"] - poi) / poi >= OI_MOVE_FRAC:
            oi_moves.append({"sym": s, "oi_chg_pct": round(100 * (v["oi"] - poi) / poi, 1)})
    surges.sort(key=lambda d: -d["ratio"])
    oi_moves.sort(key=lambda d: -abs(d["oi_chg_pct"]))

    prev_syms = set(prev_marks)
    new_listings = sorted(set(stats) - prev_syms) if prev_syms else []
    delisted = sorted(prev_syms - set(stats)) if prev_syms else []

    payload = {
        "updated": now_iso(), "ttl_sec": TTL_SEC,
        "n_books": len(stats), "n_liquid": len(liquid),
        "tickets": strategy_tickets(stats, lighter_apr, divergence),
        "stress": stress,
        "prem_outliers": prem_outliers,
        "funding_extremes": funding_extremes,
        "funding_divergence": divergence[:5],
        "vol_surges": surges[:TOP_N],
        "oi_moves": oi_moves[:TOP_N],
        "new_listings": new_listings[:20],
        "delisted": delisted[:20],
        # [2026-07-15 BRAIN LENS-FORWARD] compact liquid-book price map that
        # SURVIVES into bot_state_history (unlike _marks) — the brain joins
        # each ticket@T with marks@T+h to grade every lens counterfactually
        # on forward returns, not just the ~6 tickets the taker trades.
        "marks": {s: float(f'{v["last"]:.6g}')
                  for s, v in liquid.items() if v.get("last")},
        # compact diff base for the NEXT run (all active books, not just liquid,
        # so listings/delistings diff over the full set)
        "_marks": {s: [round(v["qvol"], 2), round(v["oi"], 4)]
                   for s, v in stats.items()},
    }
    return payload


# ---------------------------------------------------------------------------


def main():
    try:
        obd = _get("/api/v1/orderBookDetails")
        fr = _get("/api/v1/funding-rates")
    except Exception as e:  # noqa: BLE001 — WAF/timeout: skip this run quietly
        print(f"[lighter-scout] {now_iso()} fetch failed (skipping): {e!r}")
        return
    stats = book_stats(obd.get("order_book_details") or [], MIN_QVOL)
    if not stats:
        print(f"[lighter-scout] {now_iso()} no active books parsed — skipping")
        return
    lighter_apr, other_aprs = funding_aprs(fr.get("funding_rates") or [])

    prev = store.load_state(KEY) or {}
    payload = build_snapshot(stats, lighter_apr, other_aprs, prev.get("_marks") or {})
    store.save_state(KEY, payload)
    hist = {k: v for k, v in payload.items() if k != "_marks"}
    store.save_history(KEY, hist)

    st = payload["stress"] or {}
    fx = ", ".join(f"{x['sym']}@{x['apr_pct']}%"
                   for x in payload["funding_extremes"][:2]) or "n/a"
    dv = ", ".join(f"{x['sym']}{x['gap_pct']:+}pp"
                   for x in payload["funding_divergence"][:2]) or "n/a"
    tk = payload["tickets"]
    print(f"[lighter-scout] {now_iso()} books={payload['n_books']} "
          f"liquid={payload['n_liquid']} | stress med={st.get('med')} "
          f"p90={st.get('p90')} max={st.get('max')}bps "
          f"| funding: {fx} | diverge: {dv} "
          f"| tickets: brk={len(tk['breakout'])} dip={len(tk['dip'])} "
          f"momo={len(tk['momentum'])} div={len(tk.get('divergence') or [])} "
          f"| new={len(payload['new_listings'])} surge={len(payload['vol_surges'])}")


# ---------------------------------------------------------------------------


def selftest():
    print("Running Lighter Scout offline self-test...\n")
    books = [
        {"symbol": "BTC", "status": "active", "mark_price": 62430.0,
         "index_price": 62461.3, "daily_quote_token_volume": 5e8, "open_interest": 1000.0},
        {"symbol": "RKLB", "status": "active", "mark_price": 100.26,
         "index_price": 100.0, "daily_quote_token_volume": 3e5, "open_interest": 50.0},
        {"symbol": "DEAD", "status": "active", "mark_price": 110.0,
         "index_price": 100.0, "daily_quote_token_volume": 5e3, "open_interest": 1.0},
        {"symbol": "HALT", "status": "inactive", "mark_price": 1, "index_price": 1,
         "daily_quote_token_volume": 9e9},
        {"symbol": "BROKEN", "status": "active", "mark_price": None, "index_price": 1},
    ]
    stats = book_stats(books, 1e5)
    assert set(stats) == {"BTC", "RKLB", "DEAD"}, stats
    assert stats["BTC"]["liquid"] and not stats["DEAD"]["liquid"]

    rates = [
        {"symbol": "BTC", "exchange": "lighter", "rate": 0.0000114},     # ~10% APR
        {"symbol": "BTC", "exchange": "binance", "rate": 0.0000114},
        {"symbol": "RKLB", "exchange": "lighter", "rate": 0.000342},     # ~300% APR
        {"symbol": "RKLB", "exchange": "binance", "rate": 0.0000114},    # ~10% APR
        {"symbol": "DEAD", "exchange": "lighter", "rate": 0.005},        # extreme but illiquid
    ]
    lighter_apr, other_aprs = funding_aprs(rates)
    assert abs(lighter_apr["RKLB"] - 299.6) < 1.0, lighter_apr

    prev = {"BTC": [1e8, 800.0], "GONE": [1e6, 5.0]}
    snap = build_snapshot(stats, lighter_apr, other_aprs, prev)
    assert snap["stress"]["n"] == 2, "liquid books only in stress (BTC, RKLB)"
    syms = [x["sym"] for x in snap["funding_extremes"]]
    assert "DEAD" not in syms, "illiquid extreme funding must be excluded"
    assert syms[0] == "RKLB", "RKLB is the top liquid funding extreme"
    assert snap["funding_divergence"][0]["sym"] == "RKLB", snap["funding_divergence"]
    assert abs(snap["funding_divergence"][0]["gap_pct"] - 289.6) < 1.5
    assert snap["vol_surges"][0]["sym"] == "BTC", "5e8 vs 1e8 = 5x surge"
    assert snap["oi_moves"][0]["sym"] == "BTC", "1000 vs 800 OI = +25%"
    assert snap["new_listings"] == ["DEAD", "HALT", "RKLB"] or "RKLB" in snap["new_listings"]
    assert snap["delisted"] == ["GONE"]
    assert "_marks" in snap and "BTC" in snap["_marks"]

    # 4) Strategy tickets: each lens picks its setup, exclusions hold.
    def lb(sym, last, hi, lo, chg, qvol=5e6, prem=1.0):
        return {"prem_bps": prem, "qvol": qvol, "oi": 1.0, "liquid": qvol >= 1e5,
                "last": last, "high": hi, "low": lo, "chg": chg}
    tstats = {
        "BRK":  lb("BRK", 99.5, 100.0, 90.0, +4.0),            # at high, up
        "RICH": lb("RICH", 99.5, 100.0, 90.0, +4.0, prem=25.0),  # rich: excluded
        "DIPX": lb("DIPX", 90.4, 100.0, 90.0, -3.0),           # at low, bounded
        "KNIFE": lb("KNIFE", 90.4, 100.0, 90.0, -12.0),        # crash: excluded
        "MOMO": lb("MOMO", 95.0, 100.0, 90.0, +6.0, qvol=2e6),
        "THIN": lb("THIN", 99.9, 100.0, 90.0, +9.0, qvol=5e4),  # illiquid
    }
    tk = strategy_tickets(tstats, {"BRK": 10.0, "MOMO": 20.0})
    assert [r["sym"] for r in tk["breakout"]] == ["BRK"], tk["breakout"]
    assert [r["sym"] for r in tk["dip"]] == ["DIPX"], tk["dip"]
    momo_syms = [r["sym"] for r in tk["momentum"]]
    assert "MOMO" in momo_syms and "THIN" not in momo_syms and "RICH" not in momo_syms
    assert tk["dip"][0]["trend"] == "unknown_v1"

    # 5) Divergence tickets: side = receive the divergent rate; premium guard.
    div = [
        {"sym": "BRK", "lighter_apr": 500.0, "xvenue_apr": 10.0, "gap_pct": 490.0},
        {"sym": "DIPX", "lighter_apr": -400.0, "xvenue_apr": 5.0, "gap_pct": -405.0},
        {"sym": "MOMO", "lighter_apr": 60.0, "xvenue_apr": 10.0, "gap_pct": 50.0},   # below bar
        {"sym": "RICH", "lighter_apr": -400.0, "xvenue_apr": 5.0, "gap_pct": -405.0},  # long a rich book: skip
    ]
    tkd = strategy_tickets(tstats, {}, div)["divergence"]
    got = {(r["sym"], r["side"]) for r in tkd}
    assert got == {("BRK", "short"), ("DIPX", "long")}, tkd

    print("All Lighter Scout self-tests passed (stats, funding, diffs, tickets).")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    else:
        main()
