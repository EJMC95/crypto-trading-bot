#!/usr/bin/env python3
"""
parliament/scanners.py — Layer 2: KEATING 🔭, the scanner bench.

Ten scanners, every one reading LIGHTER'S OWN tape (the shared LighterData
layer) and nothing else. Each emits typed signals onto the bus
(`signals.<name>`) and into the ecosystem DB, where the six bots, the ML
engine and the tuners consume them. All scan math is pure compute over
plain lists — deterministic and offline-testable.

THE BENCH
   1 momentum_burst      15m 4-bar return z-score vs its own history
   2 breakout            1h Donchian break of the prior 48-bar range
   3 mean_reversion      15m RSI stretch (<25 long / >75 short)
   4 volume_spike        15m bar volume vs trailing median (ratio >= 4)
   5 funding_extreme     TRUE funding APR outliers — the RECEIVING side
   6 orderbook_imbalance ws depth imbalance (|imb| >= 0.35, fresh only)
   7 volatility_regime   1h realized-vol expansion/contraction (context)
   8 new_listing         a book that wasn't in the previous snapshot
   9 dislocation         mark-vs-index premium stretch (fade direction)
  10 trend_alignment     15m + 1h EMA(12/48) agreement

A signal is {scanner, sym, direction(+1/-1/0), strength(0..1), ts, meta}.
direction 0 = context (volatility_regime) — consumed as a feature/gate,
never an entry by itself. Emission is cooldown-deduped per (scanner, sym)
so the bus carries EVENTS, not a fire-hose of repeats.
"""
from __future__ import annotations

import logging
import math
import os
import time

log = logging.getLogger("parliament.scanners")

COOLDOWN_SEC = float(os.environ.get("PARL_SIGNAL_COOLDOWN_SEC", "900"))
FUNDING_BAR_APR = float(os.environ.get("PARL_FUNDING_BAR_APR", "20"))
DISLOC_BAR_BPS = float(os.environ.get("PARL_DISLOC_BAR_BPS", "25"))
IMB_BAR = float(os.environ.get("PARL_IMB_BAR", "0.35"))
VOL_SPIKE_RATIO = float(os.environ.get("PARL_VOL_SPIKE_RATIO", "4.0"))
MIN_QVOL_SIGNAL = float(os.environ.get("PARL_MIN_QVOL", "1000000"))


# ---------------------------------------------------------------------------
# pure indicator helpers (no numpy — lists in, floats out)
# ---------------------------------------------------------------------------

def ema(vals: list[float], span: int) -> float | None:
    if len(vals) < span:
        return None
    k = 2.0 / (span + 1.0)
    e = sum(vals[:span]) / span
    for v in vals[span:]:
        e = v * k + e * (1.0 - k)
    return e


def rsi(closes: list[float], period: int = 14) -> float | None:
    if len(closes) < period + 1:
        return None
    gains = losses = 0.0
    for i in range(1, period + 1):
        d = closes[i] - closes[i - 1]
        gains += max(d, 0.0)
        losses += max(-d, 0.0)
    ag, al = gains / period, losses / period
    for i in range(period + 1, len(closes)):
        d = closes[i] - closes[i - 1]
        ag = (ag * (period - 1) + max(d, 0.0)) / period
        al = (al * (period - 1) + max(-d, 0.0)) / period
    if al == 0:
        return 100.0
    return 100.0 - 100.0 / (1.0 + ag / al)


def realized_vol(closes: list[float]) -> float | None:
    if len(closes) < 3:
        return None
    rets = [math.log(closes[i] / closes[i - 1])
            for i in range(1, len(closes)) if closes[i - 1] > 0]
    if len(rets) < 2:
        return None
    mu = sum(rets) / len(rets)
    var = sum((r - mu) ** 2 for r in rets) / (len(rets) - 1)
    return math.sqrt(var)


def zscore(x: float, series: list[float]) -> float | None:
    if len(series) < 8:
        return None
    mu = sum(series) / len(series)
    var = sum((v - mu) ** 2 for v in series) / (len(series) - 1)
    sd = math.sqrt(var)
    if sd <= 1e-12:
        return None
    return (x - mu) / sd


def _closes(bars: list[dict]) -> list[float]:
    return [b["c"] for b in bars]


def _sig(scanner: str, sym: str, direction: int, strength: float,
         **meta) -> dict:
    return {"scanner": scanner, "sym": sym, "direction": int(direction),
            "strength": round(max(0.0, min(1.0, strength)), 3),
            "ts": time.time(), "meta": meta}


# ---------------------------------------------------------------------------
# the ten scanners — each takes the shared LighterData, returns signals
# ---------------------------------------------------------------------------

def scan_momentum_burst(data) -> list[dict]:
    out = []
    for sym in data.watchlist:
        bars = data.get_candles(sym, _res_fast())
        closes = _closes(bars)
        if len(closes) < 40:
            continue
        rets = [closes[i] / closes[i - 4] - 1.0
                for i in range(4, len(closes))]
        if not rets:
            continue
        z = zscore(rets[-1], rets[:-1])
        if z is not None and abs(z) >= 2.0:
            out.append(_sig("momentum_burst", sym,
                            1 if z > 0 else -1, abs(z) / 4.0, z=round(z, 2)))
    return out


def scan_breakout(data) -> list[dict]:
    out = []
    for sym in data.watchlist:
        bars = data.get_candles(sym, _res_slow())
        if len(bars) < 52:
            continue
        prior, last = bars[-49:-1], bars[-1]
        hi = max(b["h"] for b in prior)
        lo = min(b["l"] for b in prior)
        rng = hi - lo
        if rng <= 0:
            continue
        if last["c"] > hi:
            out.append(_sig("breakout", sym, 1,
                            (last["c"] - hi) / rng * 4.0, level=hi))
        elif last["c"] < lo:
            out.append(_sig("breakout", sym, -1,
                            (lo - last["c"]) / rng * 4.0, level=lo))
    return out


def scan_mean_reversion(data) -> list[dict]:
    out = []
    for sym in data.watchlist:
        closes = _closes(data.get_candles(sym, _res_fast()))
        r = rsi(closes)
        if r is None:
            continue
        if r <= 25.0:
            out.append(_sig("mean_reversion", sym, 1, (25.0 - r) / 25.0,
                            rsi=round(r, 1)))
        elif r >= 75.0:
            out.append(_sig("mean_reversion", sym, -1, (r - 75.0) / 25.0,
                            rsi=round(r, 1)))
    return out


def scan_volume_spike(data) -> list[dict]:
    out = []
    for sym in data.watchlist:
        bars = data.get_candles(sym, _res_fast())
        if len(bars) < 40:
            continue
        vols = sorted(b["v"] for b in bars[-97:-1] if b["v"] > 0)
        if len(vols) < 20:
            continue
        med = vols[len(vols) // 2]
        last = bars[-1]
        if med > 0 and last["v"] / med >= VOL_SPIKE_RATIO:
            direction = 1 if last["c"] >= last["o"] else -1
            out.append(_sig("volume_spike", sym, direction,
                            min(1.0, last["v"] / med / 10.0),
                            ratio=round(last["v"] / med, 1)))
    return out


def scan_funding_extreme(data) -> list[dict]:
    """|TRUE apr| beyond the bar. Direction is the side that RECEIVES the
    funding: positive rate = longs pay shorts -> short receives (-1)."""
    out = []
    for sym, apr in (data.funding or {}).items():
        st = data.stats(sym)
        if not st or st["qvol"] < MIN_QVOL_SIGNAL:
            continue
        if abs(apr) >= FUNDING_BAR_APR:
            out.append(_sig("funding_extreme", sym, -1 if apr > 0 else 1,
                            abs(apr) / (FUNDING_BAR_APR * 4.0), apr=apr))
    return out


def scan_orderbook_imbalance(data) -> list[dict]:
    out = []
    now = time.time()
    for sym, snap in (data.ws_books or {}).items():
        if now - snap["ts"] > 60.0:
            continue
        imb = snap["imb"]
        if abs(imb) >= IMB_BAR:
            out.append(_sig("orderbook_imbalance", sym, 1 if imb > 0 else -1,
                            abs(imb), imb=round(imb, 3),
                            spread_bps=round(snap["spread_bps"], 2)))
    return out


def scan_volatility_regime(data) -> list[dict]:
    """Context signal (direction 0): realized-vol ratio recent/base per sym."""
    out = []
    for sym in data.watchlist:
        closes = _closes(data.get_candles(sym, _res_slow()))
        if len(closes) < 60:
            continue
        recent = realized_vol(closes[-24:])
        base = realized_vol(closes[-120:-24])
        if not recent or not base or base <= 0:
            continue
        ratio = recent / base
        regime = "expanding" if ratio >= 1.5 else \
                 "quiet" if ratio <= 0.67 else "normal"
        if regime != "normal":
            out.append(_sig("volatility_regime", sym, 0,
                            min(1.0, abs(math.log(ratio))),
                            ratio=round(ratio, 2), regime=regime))
    return out


def scan_new_listing(data) -> list[dict]:
    out = []
    for sym, st in (data.market or {}).items():
        if st.get("_new"):
            out.append(_sig("new_listing", sym, 1, 0.6,
                            market_id=st.get("market_id")))
    return out


def scan_dislocation(data) -> list[dict]:
    """Mark-vs-index premium stretch — Lighter's OWN index_price is the
    reference (the 17-Jul Snap Back rule). Direction fades the premium."""
    out = []
    for sym, st in (data.market or {}).items():
        if st["qvol"] < MIN_QVOL_SIGNAL or st.get("index", 0) <= 0:
            continue
        prem = st["prem_bps"]
        if abs(prem) >= DISLOC_BAR_BPS:
            out.append(_sig("dislocation", sym, -1 if prem > 0 else 1,
                            abs(prem) / (DISLOC_BAR_BPS * 4.0),
                            prem_bps=prem))
    return out


def scan_trend_alignment(data) -> list[dict]:
    out = []
    for sym in data.watchlist:
        fast_c = _closes(data.get_candles(sym, _res_fast()))
        slow_c = _closes(data.get_candles(sym, _res_slow()))
        if len(fast_c) < 60 or len(slow_c) < 60:
            continue
        f12, f48 = ema(fast_c, 12), ema(fast_c, 48)
        s12, s48 = ema(slow_c, 12), ema(slow_c, 48)
        if None in (f12, f48, s12, s48):
            continue
        fast_dir = 1 if f12 > f48 else -1
        slow_dir = 1 if s12 > s48 else -1
        if fast_dir == slow_dir:
            gap = abs(s12 - s48) / s48 if s48 else 0.0
            out.append(_sig("trend_alignment", sym, fast_dir,
                            min(1.0, gap * 50.0), gap_pct=round(gap * 100, 3)))
    return out


SCANNERS = {
    "momentum_burst": scan_momentum_burst,
    "breakout": scan_breakout,
    "mean_reversion": scan_mean_reversion,
    "volume_spike": scan_volume_spike,
    "funding_extreme": scan_funding_extreme,
    "orderbook_imbalance": scan_orderbook_imbalance,
    "volatility_regime": scan_volatility_regime,
    "new_listing": scan_new_listing,
    "dislocation": scan_dislocation,
    "trend_alignment": scan_trend_alignment,
}


def _res_fast() -> str:
    from . import data as _d
    return _d.RES_FAST


def _res_slow() -> str:
    from . import data as _d
    return _d.RES_SLOW


class ScannerEngine:
    """Runs the bench each cycle, cooldown-dedupes, publishes bus + DB."""

    def __init__(self, data, bus, db):
        self.data = data
        self.bus = bus
        self.db = db
        self._last: dict[tuple, tuple[float, float]] = {}  # (scanner,sym) -> (ts, strength)
        self.emitted = 0

    def run_once(self) -> list[dict]:
        if not self.data.fresh():
            return []
        emitted = []
        for name, fn in SCANNERS.items():
            try:
                signals = fn(self.data)
            except Exception as e:  # noqa: BLE001 — one bad scanner never
                log.warning("scanner %s failed (%s)", name, e)  # stops the bench
                continue
            for sig in signals:
                key = (name, sig["sym"])
                prev = self._last.get(key)
                now = sig["ts"]
                if prev and now - prev[0] < COOLDOWN_SEC \
                        and sig["strength"] < prev[1] * 1.25:
                    continue
                self._last[key] = (now, sig["strength"])
                emitted.append(sig)
                if self.bus is not None:
                    self.bus.publish(f"signals.{name}", sig)
                if self.db is not None:
                    self.db.add_signal(name, sig["sym"], sig["direction"],
                                       sig["strength"], sig["meta"], ts=now)
        self.emitted += len(emitted)
        return emitted

    async def run_forever(self, interval: float, beat=None):
        import asyncio
        while True:
            n = len(self.run_once())
            if beat:
                beat("keating.scanners", f"{n} signals")
            await asyncio.sleep(interval)
