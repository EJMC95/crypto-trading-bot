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
    funding            [2026-07-17] the FULL per-symbol APR cross-section over
                       every ACTIVE book — see the note on `funding` below.
                       funding_extremes is the top-8 VIEW of this; the tape
                       needs the cross-section to answer carry after the fact
    funding_basis      the units `funding` is denominated in. READ IT: every
                       APR this organ publishes is 8x TRUE, because
                       funding_aprs() annualises an 8-HOUR fraction as hourly
                       (verified vs the settled /api/v1/fundings series, ratio
                       exactly 8.00). Divide by true_apr_divisor. Deliberately
                       not corrected — the same conversion denominates the LIVE
                       Funding Farmer's gate; see the BASIS STAMP note below
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
import funding_basis

try:
    import fleet_tuning as tuning     # growth rail (optional import)
except Exception:  # noqa: BLE001
    tuning = None

KEY = "lighter-market"
TTL_SEC = 900
API_BASE = os.environ.get("LIGHTER_API_BASE", "https://mainnet.zklighter.elliot.ai")
MIN_QVOL = float(os.environ.get("SCOUT_MIN_QVOL", "100000"))   # liquid floor $/day
VOL_SURGE_RATIO = float(os.environ.get("SCOUT_VOL_SURGE", "3.0"))
OI_MOVE_FRAC = float(os.environ.get("SCOUT_OI_MOVE", "0.25"))
# Funding-divergence tickets: |Lighter APR - cross-venue median APR| must be
# at least this many percentage points to become a ticket (DATA printed
# +925pp at first light — genuine divergences are triple digits).
# [2026-07-17] /8 with the basis fix — same divergence decision, true units.
DIV_GAP_PP = float(os.environ.get("SCOUT_DIV_GAP", "37.5"))
TOP_N = 8

# ---- Lens EMISSION bars (2026-07-15 GROWTH RAIL) ----------------------------
# These gate which ADVISORY tickets are emitted — i.e. what the brain gets
# to grade counterfactually — NOT what trades (the taker's own conviction
# bars gate fills). The scout tuner may WIDEN them via bounded fleet_tuning
# levers when a lens is starving for samples: more tickets = faster lens
# learning, zero trading surface.
BRK_RANGE_MIN = float(os.environ.get("SCOUT_BRK_RANGE_MIN", "0.9"))
DIP_RANGE_MAX = float(os.environ.get("SCOUT_DIP_RANGE_MAX", "0.1"))
MOMO_CHG_MIN = float(os.environ.get("SCOUT_MOMO_CHG_MIN", "3.0"))
# [2026-07-30 SUPPLY CAP — the fleet's tightest offense constraint] 6 -> 12.
# `strategy_tickets` truncates EVERY lens to this number, and on the live bus
# `dip` and `divergence` both returned EXACTLY 6 while breakout/momentum
# returned 5 — a lens returning exactly its cap is a lens whose cap binds.
# The lens behind it is the fleet's only measured alpha (shadow
# short-divergence: +3.035%/trade vs its own regime, t=+4.04), and it was
# being handed a 6-wide candidate list from which to fill 4 slots. Every
# "closed question" on the Taker (`TT_MAX_OPEN`, `TT_DIV_GAP`, lens on/off,
# clip size, symbol eligibility) was about ALLOCATING this fixed supply;
# none of them was about ENLARGING it. Widening here changes no entry bar —
# the taker's own gates still judge every ticket — it only stops the scout
# throwing away already-graded candidates. Registry-bounded at 15.
TICKET_TOP_N = int(os.environ.get("SCOUT_TICKET_TOP_N", "12"))


def apply_tuning():
    """Growth-rail levers override the env defaults (bounded in the
    fleet_tuning registry; expired/absent levers leave defaults intact).
    Returns {lever: value} of anything that actually moved, for the log."""
    global BRK_RANGE_MIN, DIP_RANGE_MAX, MOMO_CHG_MIN, TICKET_TOP_N, DIV_GAP_PP
    if tuning is None:
        return {}
    moved = {}
    for lever, attr in (("scout.brk_range_min", "BRK_RANGE_MIN"),
                        ("scout.dip_range_max", "DIP_RANGE_MAX"),
                        ("scout.momo_chg_min", "MOMO_CHG_MIN"),
                        ("scout.ticket_top_n", "TICKET_TOP_N"),
                        # [2026-07-21 IMB-20] the winner lens's diet lever
                        ("scout.div_gap_pp", "DIV_GAP_PP")):
        cur = globals()[attr]
        val = tuning.get_lever(lever, cur)
        if val != cur:
            globals()[attr] = val
            moved[lever] = val
    return moved


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
    [2026-07-17 BASIS FIX] Lighter's `rate` is an 8-HOUR fraction, not hourly:
    APR% = rate * 3 * 365 * 100 (funding_basis.to_apr_pct). It was annualised
    as hourly here, making every apr this organ published 8x TRUE. The venue's
    floor band is 3.5% apr, not 28%. SCOUT_DIV_GAP is divided by the same 8 in
    this commit so the divergence bar keeps its meaning.
    NOTE the benchmark rows (binance/bybit/hyperliquid) come from the SAME
    endpoint and are annualised the same way here — binance/bybit are also 8h,
    so they are now RIGHT too; hyperliquid rows are hourly and are now 8x LOW.
    Only the LIGHTER value is consumed (`rate`); `_bench` feeds divergence,
    which is why div_gap is a Lighter-vs-median comparison and stays internally
    consistent. Cross-venue absolute apr is NOT a supported read off this key."""
    lighter, others = {}, {}
    for r in rates:
        try:
            sym, rate = r.get("symbol"), r.get("rate")
            if not sym or rate is None:
                continue
            apr = funding_basis.to_apr_pct(rate, 'lighter')
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


def historized(payload):
    """The append-only-history projection of a snapshot. `_marks` is the diff
    base for the NEXT run only and would bloat the tape; everything else is
    evidence and must survive. Extracted from main() [2026-07-17] so the
    selftest can pin the REAL projection — this whole organ's `marks`/`funding`
    cross-sections exist ONLY to be joined to a decision after the fact, so a
    key silently dropped here is the difference between evidence and nothing."""
    return {k: v for k, v in payload.items() if k != "_marks"}


def oracle_regimes(oracle_state, now_ts=None):
    """[2026-07-22] {sym: {"v": verdict, "dir": dir}} from a FRESH
    regime-oracle payload — the per-asset regime stamps for tickets.

    WHY: today a regime-aware taker rule is UNREPLAYABLE — the recorded
    tape carries no regime, so any future "gate lens X in risk-off" idea
    has no evidence to be judged on. Stamping each ticket with the regime
    THE ASSET was in at emission starts that tape now, at a few bytes per
    ticket. Consumes the oracle's `pairs` — the per-asset surface the (az)
    build published (crypto majors AND non-crypto, each graded on its OWN
    tape); a sym the oracle does not grade gets NO stamp — absence, never
    a wrong-class guess (the item-18 contract). Stale/absent/malformed
    oracle -> {} and tickets simply go unstamped (fail-safe). ADVISORY:
    zero consumers read the stamp; it accrues for the replay/tuner
    evidence machinery to condition on once the sample earns it."""
    st = oracle_state if isinstance(oracle_state, dict) else {}
    try:
        upd = datetime.fromisoformat(str(st.get("updated")))
        now = (now_ts if now_ts is not None
               else datetime.now(timezone.utc).timestamp())
        if now - upd.timestamp() > float(st.get("ttl_sec") or 0):
            return {}
    except (TypeError, ValueError):
        return {}
    out = {}
    for sym, p in (st.get("pairs") or {}).items():
        if isinstance(p, dict) and p.get("verdict"):
            out[sym] = {"v": p["verdict"], "dir": p.get("dir")}
    return out


def strategy_tickets(stats, lighter_apr, divergence=None, regimes=None):
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
        if rng >= BRK_RANGE_MIN and chg > 0.0 and not rich and not longs_pay_hard:
            out["breakout"].append(row)
        if rng <= DIP_RANGE_MAX and -8.0 <= chg <= -1.0 and not rich:
            out["dip"].append({**row, "trend": "unknown_v1"})
        if chg >= MOMO_CHG_MIN and v["qvol"] >= 1e6 and not rich and not longs_pay_hard:
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
    # [2026-07-22] per-asset regime stamp (see oracle_regimes): additive,
    # only where the oracle grades the sym on its OWN tape; one place for
    # all four lenses so no lens can silently miss it.
    if regimes:
        for rows in out.values():
            for r in rows:
                reg = regimes.get(r["sym"])
                if reg:
                    r["regime"] = reg
    out["breakout"].sort(key=lambda r: (-r["range_pos"], -r["vol_m"]))
    out["dip"].sort(key=lambda r: (r["range_pos"], r["chg_pct"]))
    out["momentum"].sort(key=lambda r: -r["chg_pct"])
    out["divergence"].sort(key=lambda r: -abs(r["gap_pct"]))
    return {k: v[:TICKET_TOP_N] for k, v in out.items()}


def build_snapshot(stats, lighter_apr, other_aprs, prev_marks, regimes=None):
    """Assemble the published payload from the pure inputs.
    prev_marks: {sym: [qvol, oi]} from the previous snapshot ({} first run).
    regimes: oracle_regimes() output ({} / None -> unstamped tickets)."""
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
        "tickets": strategy_tickets(stats, lighter_apr, divergence, regimes),
        "stress": stress,
        "prem_outliers": prem_outliers,
        "funding_extremes": funding_extremes,
        "funding_divergence": divergence[:5],
        "vol_surges": surges[:TOP_N],
        "oi_moves": oi_moves[:TOP_N],
        "new_listings": new_listings[:20],
        "delisted": delisted[:20],
        # [2026-07-15 BRAIN LENS-FORWARD] compact price map that SURVIVES
        # into bot_state_history (unlike _marks) — the brain joins each
        # ticket@T with marks@T+h to grade every lens counterfactually.
        # [2026-07-16 AUDIT FIX] ALL active books, not liquid-only: the live
        # taker marks and exits from the full active set, so a liquid-only
        # tape meant replayed positions whose book dropped below the volume
        # floor mid-hold could never exit and were valued at ENTRY — an
        # optimistic bias in closed_net, the exact metric the tuner and
        # incubator accept on. (~215 vs ~130 symbols; a few KB per snapshot.)
        "marks": {s: float(f'{v["last"]:.6g}')
                  for s, v in stats.items() if v.get("last")},
        # [2026-07-17 CARRY CROSS-SECTION] the FULL per-symbol funding APR over
        # every ACTIVE book, historized alongside `marks` and for the same
        # reason: only a stored cross-section can be joined to a decision after
        # the fact. Until now the ONLY funding this organ persisted was the
        # top-8 |extremes| — which is a VIEW, not the data. When Stock Leaders
        # was reviewed on 17-Jul ("it's constantly losing"), four of five
        # evidence strands could not be resolved: with no per-symbol funding
        # history there was no way to test whether the book's picks were
        # systematically expensive, or merely expensive that week. The
        # correlation had to be run on ONE live snapshot at n=25 — where most
        # names sit on the venue's floor band, so |rho| > 0.398 is needed for
        # p<0.05 and the test cannot resolve at all. That is a data gap, not a
        # hard question. `marks` was widened from liquid-only to all books on
        # 16-Jul on the identical argument (a few KB per snapshot); this is the
        # carry half of the same tape, and every long-perp design pays or earns
        # funding (Tide Rider + Funding Farmer are REAL MONEY).
        # NOT the whole story: /api/v1/fundings already serves ~31d of SETTLED
        # hourly rates retroactively. What only this key can give is depth past
        # that window, and the PREDICTED rate as seen at the decision instant.
        # COST, measured 17-Jul against the live venue, not estimated: ~201
        # active books, all carrying a rate (the funding map's 214 rows include
        # inactive books this intersection drops). ~3.0 KB/snapshot of raw JSON
        # => +47% on a 6.3 KB history row => ~52 MB at the 60-day retention
        # floor (BOT_STATE_HISTORY_KEEP_DAYS, 16-Jul audit fix), on a DB that
        # reaches ~150 MB at that steady state regardless. Those are RAW-JSON
        # figures and so conservative: jsonb TOAST-compresses this key well (it
        # is ~43 distinct values across ~201 symbols), measuring ~1.5 KB and
        # ~32 MB on disk. Bounded and worth it either way.
        # Deliberately NOT liquid-gated and NOT kill-switched: liquid-only is
        # the exact bug the 16-Jul `marks` fix repaired (a book can fall under
        # the floor while still held), and an env flag on a DATA key is just a
        # born-dark switch waiting to be flipped.
        # Keyed like `marks` (raw Lighter symbol, from the same `symbol` field)
        # so the two join directly. Joining to paper_trades/bot ledgers needs
        # venues/symbol_map.from_lighter() — 5 keys differ (the 1000X markets).
        "funding": {s: lighter_apr[s] for s in stats if s in lighter_apr},
        # [2026-07-17 BASIS STAMP — the tape describes its own units.]
        # Rows written BEFORE this fix carry true_apr_divisor 8.0: this organ
        # annualised Lighter's 8-HOUR funding fraction as if hourly, so every
        # apr it published was 8x TRUE. Rows written AFTER carry 1.0 — the
        # conversion now goes through funding_basis (rate * 3 * 365 * 100) and
        # SCOUT_DIV_GAP was divided by the same 8 in that commit, so the
        # divergence decision is unchanged.
        # VERIFIED against the SETTLED series /api/v1/fundings: ETH predicted
        # 9.6e-05 -> published 84.1%, settled 10.51%, ratio exactly 8.00; DOGE
        # and SPY likewise (SPY's floor: 28.0% published -> 3.50% TRUE).
        # KEEP THIS KEY even at 1.0: a consumer joining the 60-day tape spans
        # BOTH epochs, and the divisor is the only thing that makes the old
        # rows readable. Divide by it; never assume.
        "funding_basis": {"unit": "apr_pct",
                          "true_apr_divisor": 1.0,
                          "src": "funding-rates.rate (8h fraction)",
                          "corrected": "2026-07-17",
                          "note": ("apr is TRUE from 2026-07-17; rows stamped "
                                   "8.0 predate the fix — divide those by 8")},
        # [2026-07-30 FLEET UNIVERSE] PUBLIC per-symbol 24h $volume in $M, all
        # active books. The data already existed in `_marks` below, but that
        # key is documented as "compact diff base for the NEXT run" — a
        # private implementation detail no consumer should bind to. Five
        # books were carrying hand-typed watchlists (Counterweight ranked 30
        # of 202, Snap Back 16, Tide Rider 6, Index Rider 3) purely because
        # there was no supported read of "what does the venue actually
        # trade, and how big is each book". `fleet_bus.scout_universe()` is
        # that read; this is the field behind it. Prefer this key; the
        # accessor still falls back to `_marks` so a consumer shipped ahead
        # of the scout's next deploy is not dark in the meantime.
        "vols": {s: round((v.get("qvol") or 0.0) / 1e6, 4)
                 for s, v in stats.items()},
        # compact diff base for the NEXT run (all active books, not just liquid,
        # so listings/delistings diff over the full set)
        "_marks": {s: [round(v["qvol"], 2), round(v["oi"], 4)]
                   for s, v in stats.items()},
    }
    return payload


# ---------------------------------------------------------------------------


def main():
    moved = apply_tuning()
    if moved:
        print(f"[lighter-scout] {now_iso()} growth-rail levers active: {moved}")
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
    regimes = oracle_regimes(store.load_state("regime-oracle"))
    payload = build_snapshot(stats, lighter_apr, other_aprs,
                             prev.get("_marks") or {}, regimes)
    store.save_state(KEY, payload)
    store.save_history(KEY, historized(payload))

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
          f"| new={len(payload['new_listings'])} surge={len(payload['vol_surges'])} "
          f"| regime-stamps from {len(regimes)} oracle-graded books")


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
    assert abs(lighter_apr["RKLB"] - 37.45) < 0.5, lighter_apr  # 8h basis: TRUE

    prev = {"BTC": [1e8, 800.0], "GONE": [1e6, 5.0]}
    snap = build_snapshot(stats, lighter_apr, other_aprs, prev)
    assert snap["stress"]["n"] == 2, "liquid books only in stress (BTC, RKLB)"
    syms = [x["sym"] for x in snap["funding_extremes"]]
    assert "DEAD" not in syms, "illiquid extreme funding must be excluded"
    assert syms[0] == "RKLB", "RKLB is the top liquid funding extreme"
    assert snap["funding_divergence"][0]["sym"] == "RKLB", snap["funding_divergence"]
    assert abs(snap["funding_divergence"][0]["gap_pct"] - 36.2) < 1.5
    assert snap["vol_surges"][0]["sym"] == "BTC", "5e8 vs 1e8 = 5x surge"
    assert snap["oi_moves"][0]["sym"] == "BTC", "1000 vs 800 OI = +25%"
    assert snap["new_listings"] == ["DEAD", "HALT", "RKLB"] or "RKLB" in snap["new_listings"]
    assert snap["delisted"] == ["GONE"]
    assert "_marks" in snap and "BTC" in snap["_marks"]

    # [2026-07-17 CARRY CROSS-SECTION] `funding` is the DATA; funding_extremes
    # is a top-8 liquid VIEW of it. DEAD is illiquid and so is correctly absent
    # from the view (asserted above) — but it MUST be present here, or the tape
    # can only ever answer questions about the coins that were already loud.
    assert set(snap["funding"]) == {"BTC", "RKLB", "DEAD"}, snap["funding"]
    assert "HALT" not in snap["funding"], "inactive book carries no funding"
    assert abs(snap["funding"]["RKLB"] - 37.45) < 0.5, snap["funding"]
    # must be joinable to `marks` (same key space) — that join IS the use case
    assert set(snap["funding"]) <= set(stats), "funding/marks key spaces diverged"
    assert set(snap["marks"]) <= set(stats)
    # the BASIS STAMP must ride with the data — an 8x-wrong APR that travels
    # WITHOUT its divisor is exactly how a tape becomes 60 days of false fact
    # post-fix the tape is TRUE (divisor 1.0); the key must SURVIVE anyway —
    # a 60-day join spans both epochs and only the divisor makes old rows read.
    assert snap["funding_basis"]["true_apr_divisor"] == 1.0, snap["funding_basis"]
    assert snap["funding_basis"]["corrected"] == "2026-07-17"
    # and the conversion itself must now be TRUE: RKLB ~300%apr the OLD way
    assert abs(snap["funding"]["RKLB"] - 37.4) < 1.0, snap["funding"]
    assert "funding_basis" in historized(snap), "basis stamp must survive history"
    # ...and must SURVIVE into history, or none of the above is worth anything
    _h = historized(snap)
    assert "funding" in _h and _h["funding"] == snap["funding"], "history drops funding"
    assert "marks" in _h and "_marks" not in _h, _h.keys()

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
    # [2026-07-17 BASIS FIX] fixture apr/gap values RE-DENOMINATED /8 with
    # DIV_GAP_PP (300 -> 37.5). The INTENT is what is pinned, not the digits:
    # BRK/DIPX clear the bar, MOMO sits BELOW it, RICH is skipped on premium.
    # Left in old units, MOMO's 50pp gap would have cleared the new 37.5 bar
    # and silently inverted this test's meaning — the fixture is denominated
    # in the same units as the threshold it exercises.
    div = [
        {"sym": "BRK", "lighter_apr": 62.5, "xvenue_apr": 1.25, "gap_pct": 61.25},
        {"sym": "DIPX", "lighter_apr": -50.0, "xvenue_apr": 0.625, "gap_pct": -50.625},
        {"sym": "MOMO", "lighter_apr": 7.5, "xvenue_apr": 1.25, "gap_pct": 6.25},   # below the 37.5 bar
        {"sym": "RICH", "lighter_apr": -50.0, "xvenue_apr": 0.625, "gap_pct": -50.625},  # long a rich book: skip
    ]
    tkd = strategy_tickets(tstats, {}, div)["divergence"]
    got = {(r["sym"], r["side"]) for r in tkd}
    assert got == {("BRK", "short"), ("DIPX", "long")}, tkd

    # 6) [2026-07-22] Per-asset regime stamps on tickets (oracle_regimes).
    # Fresh oracle + covered sym -> stamped on EVERY lens incl. divergence;
    # uncovered sym -> NO stamp (absence, never a wrong-class guess);
    # stale/absent/malformed oracle -> {} and tickets identical to today.
    _now = datetime.now(timezone.utc).timestamp()
    _ost = {"updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "ttl_sec": 7200,
            "pairs": {"BRK": {"verdict": "SHORT-window", "dir": -1,
                              "adx": 30.0, "class": "crypto"},
                      "MOMO": {"verdict": "LONG-window", "dir": 1}}}
    regs = oracle_regimes(_ost, now_ts=_now)
    assert regs == {"BRK": {"v": "SHORT-window", "dir": -1},
                    "MOMO": {"v": "LONG-window", "dir": 1}}, regs
    tk_r = strategy_tickets(tstats, {"BRK": 10.0, "MOMO": 20.0}, div, regs)
    _brk = [r for r in tk_r["breakout"] if r["sym"] == "BRK"][0]
    _momo = [r for r in tk_r["momentum"] if r["sym"] == "MOMO"][0]
    _dbrk = [r for r in tk_r["divergence"] if r["sym"] == "BRK"][0]
    assert _brk["regime"]["v"] == "SHORT-window" and _brk["regime"]["dir"] == -1
    assert _momo["regime"]["v"] == "LONG-window"
    assert _dbrk["regime"]["v"] == "SHORT-window", "divergence lens stamped too"
    _dipx = [r for r in tk_r["divergence"] if r["sym"] == "DIPX"][0]
    assert "regime" not in _dipx, "uncovered sym must carry NO stamp"
    # stale / absent / malformed oracle: no stamps, tickets bit-identical
    assert oracle_regimes(dict(_ost, updated="2026-01-01T00:00:00+00:00"),
                          now_ts=_now) == {}
    assert oracle_regimes(None) == {} and oracle_regimes({}) == {}
    assert oracle_regimes({"updated": "garbage", "ttl_sec": 900,
                           "pairs": {"X": {"verdict": "LONG-window"}}}) == {}
    assert strategy_tickets(tstats, {"BRK": 10.0, "MOMO": 20.0}, div, {}) == \
        strategy_tickets(tstats, {"BRK": 10.0, "MOMO": 20.0}, div), \
        "no oracle -> tickets exactly as before"

    print("All Lighter Scout self-tests passed (stats, funding, diffs, "
          "tickets, per-asset regime stamps incl. fail-safe dark-oracle).")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    else:
        main()
