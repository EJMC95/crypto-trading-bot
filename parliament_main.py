#!/usr/bin/env python3
"""
parliament_main.py — 🏛️ supervisor for the Parliament (see parliament/).

Six layers, one asyncio process, launched from run_all.sh in the
freqtrade-bots container (shadow-only: no keys, no signing, no orders):
  L1 data      LighterData REST poller + candle refreshers + optional ws
  L2 scanners  Keating's bench of 10 (parliament/scanners.py)
  L3 ml        Keating's 5-model ensemble trainer (parliament/ml.py)
  L4 bots      the six PM shadow books (parliament/strategies.py)
  L5 tuners    the tuner bench, one lever at a time (parliament/tuners.py)
  L6 howard    the ecosystem brain: memory, cross-bot, health

Every task runs under a restart-on-crash wrapper; Howard notices the
quiet-but-alive failures the wrapper can't see. PARLIAMENT_ENABLED=0 idles
the whole chamber (prints why, keeps the loop slot — the Trail Blazer
guard pattern: never exit into a restart loop).

USAGE
    python3 parliament_main.py               # run the chamber
    python3 parliament_main.py --once        # one full cycle, then exit
    python3 parliament_main.py --selftest    # offline invariants (no net/DB)
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
import time

# repo root importability (bot_pnl_store, fleet_bus, paper_broker …) when
# invoked by path from another CWD
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from parliament import PM_BOTS  # noqa: E402
from parliament.bus import EcosystemBus  # noqa: E402
from parliament.ecosystem_db import EcosystemDB  # noqa: E402
from parliament.data import (LighterData, SCAN_SEC, CANDLE_FAST_SEC,  # noqa: E402
                             CANDLE_SLOW_SEC, RES_FAST, RES_SLOW)
from parliament.scanners import ScannerEngine  # noqa: E402
from parliament.ml import MLEngine  # noqa: E402
from parliament.strategies import build_bots  # noqa: E402
from parliament.tuners import TunerBench  # noqa: E402
from parliament.brain import Howard  # noqa: E402

log = logging.getLogger("parliament")


async def _supervised(name: str, factory, restart_sec: float = 30.0):
    """Restart-on-crash wrapper. A task that RETURNS (deliberate stop, e.g.
    ws accelerator without the wheel) is not restarted."""
    while True:
        try:
            await factory()
            log.info("task %s finished — not restarting", name)
            return
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            log.exception("task %s crashed (%s) — restart in %.0fs",
                          name, e, restart_sec)
            await asyncio.sleep(restart_sec)


def build_chamber(fetch=None, db_path: str | None = None):
    """Construct every layer, wired together. `fetch`/`db_path` are the
    injection points the selftest uses."""
    db = EcosystemDB(path=db_path)
    bus = EcosystemBus()
    data = LighterData(db=db, bus=bus, fetch=fetch)
    ml = MLEngine(db)
    tuners = TunerBench(db, bus, data)
    howard = Howard(db, bus, ml, tuners, bots=[])
    bots = build_bots(data, bus, db, ml, howard)
    howard.bots = bots
    scanners = ScannerEngine(data, bus, db)
    return {"db": db, "bus": bus, "data": data, "ml": ml, "tuners": tuners,
            "howard": howard, "bots": bots, "scanners": scanners}


async def run_chamber():
    c = build_chamber()
    data, howard, scanners = c["data"], c["howard"], c["scanners"]
    ml, tuners, bots = c["ml"], c["tuners"], c["bots"]
    beat = howard.beat
    params_fn = tuners.effective_params
    log.info("🏛️ Parliament in session: %d books %s | watch core %s",
             len(bots), list(PM_BOTS), data.watchlist)
    ml.train_from_db()      # restart-proof memory before the first entry
    tasks = [
        asyncio.create_task(_supervised(
            "data.market", lambda: data.poll_market_forever(beat=beat))),
        asyncio.create_task(_supervised(
            "data.candles.fast",
            lambda: data.poll_candles_forever(RES_FAST, CANDLE_FAST_SEC,
                                              beat=beat))),
        asyncio.create_task(_supervised(
            "data.candles.slow",
            lambda: data.poll_candles_forever(RES_SLOW, CANDLE_SLOW_SEC,
                                              beat=beat))),
        asyncio.create_task(_supervised(
            "data.ws", lambda: data.ws_forever(beat=beat))),
        asyncio.create_task(_supervised(
            "keating.scanners",
            lambda: scanners.run_forever(SCAN_SEC, beat=beat))),
        asyncio.create_task(_supervised(
            "keating.ml", lambda: ml.run_forever(beat=beat))),
        asyncio.create_task(_supervised(
            "tuners", lambda: tuners.run_forever(bots, beat=beat))),
        asyncio.create_task(_supervised(
            "howard", lambda: howard.run_forever(data=data,
                                                 scanners=scanners))),
    ]
    for bot in bots:
        tasks.append(asyncio.create_task(_supervised(
            f"bot.{bot.base}",
            lambda b=bot: b.run_forever(beat=beat, params_fn=params_fn))))
    await asyncio.gather(*tasks)


async def run_once():
    """One full cycle against the real venue — a smoke test, not a trade
    session (entries can happen; it is a shadow book either way)."""
    c = build_chamber()
    data, scanners, howard = c["data"], c["scanners"], c["howard"]
    ok = await data.refresh_market()
    print(f"market refresh: {'ok' if ok else 'FAILED'} "
          f"({len(data.market)} books, watchlist {data.watchlist})")
    if ok:
        n = await data.refresh_candles(RES_FAST)
        print(f"candles({RES_FAST}): {n} bars")
        sigs = scanners.run_once()
        print(f"scanners: {len(sigs)} signals")
        for s in sigs[:10]:
            print(f"  {s['scanner']:22s} {s['sym']:8s} dir={s['direction']:+d} "
                  f"strength={s['strength']}")
        for bot in c["bots"]:
            await bot.cycle()
        howard.refresh_stress()
        payload = howard.publish(data=data, scanners=scanners)
        print(f"howard: stress={payload['stress']} "
              f"stalled={payload['health']['stalled']}")


# ═══════════════════════════════════════════════════════════════════════════
# offline selftest — no network, no Postgres, deterministic
# ═══════════════════════════════════════════════════════════════════════════

def _synth_candles(n: int, start_px: float = 100.0, drift: float = 0.0,
                   amp: float = 0.0, period: int = 20, res_sec: int = 900,
                   end_ts: float | None = None) -> list[dict]:
    import math
    end_ts = end_ts or time.time()
    out = []
    px = start_px
    for i in range(n):
        t = int(end_ts - (n - 1 - i) * res_sec)
        px = start_px * (1 + drift * i / n) \
            * (1 + amp * math.sin(2 * math.pi * i / period))
        out.append({"t": t, "o": px * 0.999, "h": px * 1.004,
                    "l": px * 0.996, "c": px, "v": 100.0})
    return out


def _seed_data(data: LighterData) -> None:
    now = time.time()
    data.market = {
        "BTC": {"market_id": 0, "mark": 100.0, "index": 100.0, "last": 100.0,
                "prem_bps": 0.0, "qvol": 5e7, "oi": 1e6, "high": 104.0,
                "low": 96.0, "chg": 0.01, "_new": False},
        "ETH": {"market_id": 1, "mark": 50.0, "index": 49.8, "last": 50.0,
                "prem_bps": 40.2, "qvol": 3e7, "oi": 5e5, "high": 51.0,
                "low": 48.0, "chg": 0.02, "_new": False},
        "NEWCOIN": {"market_id": 99, "mark": 1.0, "index": 1.0, "last": 1.0,
                    "prem_bps": 0.0, "qvol": 2e6, "oi": 1e4, "high": 1.1,
                    "low": 0.9, "chg": 0.05, "_new": True},
    }
    data.funding = {"BTC": 3.0, "ETH": 45.0}
    data.watchlist = ["BTC", "ETH"]
    data.market_ts = now
    # BTC: strong uptrend on both TFs; ETH: flat with a fresh oversold dip
    data.candles[("BTC", RES_FAST)] = _synth_candles(160, 100.0, drift=0.10)
    data.candles[("BTC", RES_SLOW)] = _synth_candles(160, 100.0, drift=0.15,
                                                     res_sec=3600)
    eth_fast = _synth_candles(160, 50.0, amp=0.0)
    for b in eth_fast[-6:]:
        for k in ("o", "h", "l", "c"):
            b[k] *= 0.94          # 6-bar slump -> RSI floor
    data.candles[("ETH", RES_FAST)] = eth_fast
    data.candles[("ETH", RES_SLOW)] = _synth_candles(160, 50.0, res_sec=3600)
    data.ws_books["BTC"] = {"ts": now, "imb": 0.55, "spread_bps": 2.0,
                            "mid": 100.0}


async def _selftest_async() -> None:
    from parliament import strategies as strat_mod
    from parliament.scanners import SCANNERS
    from parliament.ml import MIN_READY_SAMPLES, featurize
    from parliament.strategies import PARAM_BOUNDS
    from parliament.tuners import simulate_exit
    import parliament.strategies as S

    c = build_chamber(fetch=lambda path, **kw: {}, db_path=":memory:")
    data, scanners, ml = c["data"], c["scanners"], c["ml"]
    tuners, howard, bots = c["tuners"], c["howard"], c["bots"]
    _seed_data(data)

    # -- scanners: the bench fires on the crafted tape ------------------------
    sigs = scanners.run_once()
    by = {}
    for s in sigs:
        by.setdefault(s["scanner"], []).append(s)
    assert len(SCANNERS) == 10, "spec: ten scanners on the bench"
    assert any(s["sym"] == "BTC" and s["direction"] == 1
               for s in by.get("trend_alignment", [])), "BTC uptrend must align"
    assert any(s["sym"] == "ETH" and s["direction"] == 1
               for s in by.get("mean_reversion", [])), "ETH dip must read oversold"
    assert any(s["sym"] == "ETH" for s in by.get("funding_extreme", [])), \
        "ETH 45%% apr must trip the funding bar"
    assert any(s["sym"] == "ETH" for s in by.get("dislocation", [])), \
        "ETH 40bps premium must trip dislocation"
    assert any(s["sym"] == "NEWCOIN" for s in by.get("new_listing", [])), \
        "fresh book must emit new_listing"
    assert any(s["sym"] == "BTC" for s in by.get("orderbook_imbalance", [])), \
        "0.55 imbalance must emit"
    # cooldown: an identical immediate rescan emits nothing new
    assert scanners.run_once() == [], "cooldown must dedupe identical signals"
    print(f"parliament.scanners selfcheck OK ({len(sigs)} signals, "
          f"{len(by)} scanners fired)")

    # -- ML: cold neutral, warm learns, reduce-only ---------------------------
    p, ready = ml.predict({"direction": 1})
    assert (p, ready) == (0.5, False), "cold model must be neutral"
    if ml.enabled:
        import random
        rng = random.Random(7)
        for _ in range(MIN_READY_SAMPLES + 200):
            f = {k: rng.uniform(-1, 1) for k in
                 ("direction", "ret4", "rsi_n", "vol_ratio", "funding_apr_n",
                  "prem_n", "imb", "trend", "strength", "hour_sin", "hour_cos")}
            won = (f["trend"] + 0.5 * f["ret4"] + 0.2 * rng.gauss(0, 1)) > 0
            ml.learn(f, won)
        up = {k: 0.0 for k in f} | {"trend": 0.9, "ret4": 0.5}
        dn = {k: 0.0 for k in f} | {"trend": -0.9, "ret4": -0.5}
        p_up, r_up = ml.predict(up)
        p_dn, r_dn = ml.predict(dn)
        assert r_up and r_dn and p_up > 0.6 > 0.4 > p_dn, \
            f"ensemble must learn the planted edge (p_up={p_up:.2f}, p_dn={p_dn:.2f})"
        snap = ml.snapshot()
        assert snap["ready"] and 0 < min(snap["oos_acc"].values()) <= 1
        print(f"parliament.ml selfcheck OK (p_up={p_up:.2f} p_dn={p_dn:.2f} "
              f"oos={snap['oos_acc']})")
    else:
        print("parliament.ml SKIPPED (numpy absent) — neutral verified")

    # -- bots: entry gates, accounting, exits, tags ---------------------------
    albo = next(b for b in bots if b.base == "pm-albanese")
    albo._restored = True
    now = time.time()
    albo.signals[("signals.trend_alignment", "BTC")] = {
        "scanner": "trend_alignment", "sym": "BTC", "direction": 1,
        "strength": 0.8, "ts": now, "meta": {}}
    albo.signals[("signals.momentum_burst", "BTC")] = {
        "scanner": "momentum_burst", "sym": "BTC", "direction": 1,
        "strength": 0.7, "ts": now, "meta": {}}

    # (a) the fleet L2 long-budget veto blocks the long
    if strat_mod.fleet_bus is not None:
        orig = strat_mod.fleet_bus.long_entries_blocked
        strat_mod.fleet_bus.long_entries_blocked = lambda *a, **k: True
        await albo.cycle()
        assert not albo.broker.pos, "L2 veto must block the long entry"
        strat_mod.fleet_bus.long_entries_blocked = orig
    # (b) Howard's stress pause blocks
    howard.stress_pause = True
    await albo.cycle()
    assert not albo.broker.pos, "venue-stress pause must block entries"
    howard.stress_pause = False
    # (c) gates clear -> the entry books, sized <= the configured clip
    await albo.cycle()
    assert "BTC" in albo.broker.pos, "entry must book once gates clear"
    meta = albo.open_meta["BTC"]
    assert meta["tag"] == "long-trend"
    assert meta["usd"] <= S.ORDER_USD + 1e-9, "sizing is reduce-only"
    assert albo.broker.pos["BTC"][1] > 100.0, "buy must pay the slip"
    eq_open = albo.broker.equity()
    # (d) price to TP -> close carries the taker-style composite tag
    data.market["BTC"]["last"] = meta["tp"] * 1.001
    await albo.cycle()
    assert not albo.broker.pos and albo.wins == 1
    closed = c["db"].closed_trades(bot="pm-albanese")
    assert len(closed) == 1 and closed[0]["reason"] == "tp"
    assert closed[0]["tag"] == "long-trend"
    assert albo.broker.equity() > eq_open, "TP close must realize a gain"
    # (e) daily-loss halt blocks re-entry
    albo.last_entry.clear()
    albo.day_anchor = (albo.broker.realized - albo.broker.fees) \
        + S.DAILY_HALT_USD + 1.0
    albo.signals[("signals.trend_alignment", "BTC")]["ts"] = time.time()
    albo.signals[("signals.momentum_burst", "BTC")]["ts"] = time.time()
    await albo.cycle()
    assert not albo.broker.pos, "daily-loss halt must block entries"
    albo.day_anchor = albo.broker.realized - albo.broker.fees
    print("parliament.strategies selfcheck OK (veto, stress, entry, tp, halt)")

    # -- tuners: replay gate, bounds cage, one-at-a-time ----------------------
    db = c["db"]
    end = time.time()
    # a tape that runs UP 8% then gives it all back: a tighter hold banks it
    tape = _synth_candles(96, 100.0, amp=0.04, period=96, res_sec=900,
                          end_ts=end)
    db.store_candles("SYN", "15m", tape)
    for i in range(14):
        opened = tape[4 + i]["t"]
        db.record_trade(f"syn-{i}", "pm-abbott", "parliament", "SYN", "long",
                        "long-burst", opened, opened + 40000, tape[4 + i]["c"],
                        tape[40]["c"], 0.25, -0.5, "hold", {"trend": 0.1})
    sim = simulate_exit(1, 100.0, tape[4]["t"], tape, 0.02, 0.5, 96.0)
    assert sim is not None and sim[1] == "tp", "sim must find the +2%% touch"
    lever = tuners.tune_bot("pm-abbott",
                            {"tp_pct": 0.06, "sl_pct": 0.045,
                             "max_hold_hr": 90.0, "entry_bar": 0.6,
                             "ml_gate": 0.45})
    assert lever is not None, "replay gate should enact on the crafted tape"
    lo, hi = PARAM_BOUNDS[lever["param"]]
    assert lo <= lever["value"] <= hi, "lever must live inside the cage"
    assert tuners.tune_bot("pm-abbott", {"tp_pct": 0.06, "sl_pct": 0.045,
                                         "max_hold_hr": 90.0,
                                         "entry_bar": 0.6,
                                         "ml_gate": 0.45}) is None, \
        "one lever at a time per bot"
    eff = tuners.effective_params("pm-abbott",
                                  {"tp_pct": 0.06, "sl_pct": 0.045,
                                   "max_hold_hr": 90.0, "entry_bar": 0.6,
                                   "ml_gate": 0.45})
    assert eff[lever["param"]] == lever["value"], \
        "active lever must overlay effective params"
    # starving book -> one bounded entry_bar widening
    starve = tuners.tune_bot("pm-gillard",
                             {"tp_pct": 0.01, "sl_pct": 0.01,
                              "max_hold_hr": 6.0, "entry_bar": 0.5,
                              "ml_gate": 0.45})
    assert starve is not None and starve["param"] == "entry_bar" \
        and starve["value"] < 0.5, "starving book widens its diet"
    print(f"parliament.tuners selfcheck OK (enacted {lever['param']}="
          f"{lever['value']:.4g}, starving widen {starve['value']:.3g})")

    # -- Howard: health + publish contract ------------------------------------
    howard.beat("bot.pm-albanese", "ok")
    payload = howard.publish(data=data, scanners=scanners)
    assert payload["ttl_sec"] == 900 and payload["updated"]
    assert "pm-albanese" in payload["books"]
    assert payload["books"]["pm-albanese"]["closed"] == 1
    assert payload["roster"]["brain"] == "howard"
    assert len(payload["roster"]["books"]) == 6
    from parliament.brain import EXPECTED_BEATS
    howard.started = time.time() - 10 * 3600
    stalled = howard.stalled()
    assert "bot.pm-albanese" not in stalled, "fresh beat is not stalled"
    assert "keating.ml" in stalled, "never-beaten organ must be stalled"
    assert len(EXPECTED_BEATS) >= 15
    # featurize is None-safe on an empty book
    f = featurize("GHOST", 1, data, None)
    assert all(isinstance(v, float) for v in f.values())
    print("parliament.brain selfcheck OK (health, publish contract)")


def selftest() -> None:
    t0 = time.time()
    from parliament import bus as bus_mod
    from parliament import ecosystem_db as db_mod
    bus_mod.selfcheck()          # these two spin their own event loop,
    db_mod.selfcheck()           # so they run before asyncio.run below
    asyncio.run(_selftest_async())
    print(f"parliament selftest OK — all six layers, offline, "
          f"{time.time() - t0:.1f}s")


def main() -> None:
    logging.basicConfig(
        level=os.environ.get("PARL_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(name)s %(levelname)s %(message)s")
    if "--selftest" in sys.argv:
        selftest()
        return
    if os.environ.get("PARLIAMENT_ENABLED", "1").strip() in ("0", "false", "no"):
        # Guard, not exit: run_all.sh would relaunch an exiting process every
        # 30s forever (the Trail Blazer restart-loop lesson) — idle instead.
        print("PARLIAMENT_ENABLED=0 — the chamber is prorogued; idling. "
              "Set PARLIAMENT_ENABLED=1 (or unset) to resume.")
        while True:
            time.sleep(3600)
    if "--once" in sys.argv:
        asyncio.run(run_once())
        return
    asyncio.run(run_chamber())


if __name__ == "__main__":
    main()
