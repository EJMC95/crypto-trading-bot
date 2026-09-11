"""Deterministic synthetic tapes, for tests and for the offline demo.

WHY SYNTHETIC DATA IS ALLOWED TO EXIST HERE AND IS NOT ALLOWED TO CONCLUDE
ANYTHING: a generated downtrend is a tape whose regime this file chose. Running
a short-biased system on it and reporting a profit measures the generator, not
the strategy. So the CLI labels every synthetic result as a SMOKE TEST and the
robustness gate is still applied to it -- if a rule cannot survive a market the
generator built to suit it, that is worth knowing early.

What it IS for: proving the machinery runs end to end offline -- regime
transitions fire, stops attach, budgets bite, the report renders -- with no
network, no venue and no credentials.
"""
from __future__ import annotations

import math
import random
from typing import Sequence

from .models import Candle, Market

TF_S = {"15m": 900, "1h": 3600, "4h": 14400, "1d": 86400}


def make_market(symbol: str, *, tick: float = 0.01, step: float = 0.001,
                max_leverage: float = 50.0) -> Market:
    base, _, rest = symbol.partition("/")
    quote = (rest.split(":")[0] or "USDT")
    return Market(symbol=symbol, base=base, quote=quote, tick_size=tick,
                  qty_step=step, min_qty=step, min_notional=5.0,
                  max_leverage=max_leverage, taker_fee=0.00055,
                  maker_fee=0.0002, quote_volume_24h=50_000_000.0,
                  status="active", contract=True)


def walk(*, bars: int, start: float, drift_per_bar: float, vol: float,
         seed: int, t0: float, tf: str,
         regime_flip_at: float | None = None,
         flip_drift: float | None = None) -> list[Candle]:
    """A geometric random walk with an optional regime flip partway through.

    The flip exists so a test can assert the regime engine actually TRANSITIONS
    rather than happening to sit in the right state for the whole tape."""
    rng = random.Random(seed)
    span = TF_S[tf]
    px = start
    out: list[Candle] = []
    for i in range(bars):
        d = drift_per_bar
        if regime_flip_at is not None and i >= int(bars * regime_flip_at):
            d = drift_per_bar if flip_drift is None else flip_drift
        shock = rng.gauss(0.0, vol)
        nxt = max(1e-6, px * math.exp(d + shock))
        o, c = px, nxt
        wick = abs(shock) * px * 0.9 + px * vol * 0.25
        h = max(o, c) + abs(rng.gauss(0.0, 1.0)) * wick * 0.5
        l = min(o, c) - abs(rng.gauss(0.0, 1.0)) * wick * 0.5
        v = 1000.0 * (1.0 + abs(shock) / max(vol, 1e-9)) * (
            1.0 + 0.3 * rng.random())
        out.append(Candle(ts=t0 + i * span, open=o, high=max(h, o, c),
                          low=min(max(l, 1e-9), o, c), close=c, volume=v))
        px = nxt
    return out


def tapes(symbols: Sequence[str], *, bars_1h: int = 1600, seed: int = 7,
          t0: float = 1_700_000_000.0, downtrend: bool = True
          ) -> dict[str, dict[str, list[Candle]]]:
    """One coherent multi-timeframe tape per symbol.

    The higher timeframes are AGGREGATED from the 15m series rather than
    generated separately -- three independent walks would disagree about the
    same instant, and the whole system is built on the three agreeing."""
    out: dict[str, dict[str, list[Candle]]] = {}
    n15 = bars_1h * 4
    for k, sym in enumerate(symbols):
        drift = (-0.0006 if downtrend else 0.0006) * (1.0 + 0.15 * k)
        base = walk(bars=n15, start=100.0 * (1.0 + k), drift_per_bar=drift / 4.0,
                    vol=0.004, seed=seed + k, t0=t0, tf="15m",
                    regime_flip_at=0.45,
                    flip_drift=(-0.0016 if downtrend else 0.0012) / 4.0)
        out[sym] = {"15m": base, "1h": aggregate(base, 4, "1h"),
                    "4h": aggregate(base, 16, "4h")}
    return out


def aggregate(bars: Sequence[Candle], k: int, tf: str) -> list[Candle]:
    """Roll k bars into one. Only COMPLETE groups are emitted: a partial group
    is a forming candle, and this package never acts on one."""
    out: list[Candle] = []
    for i in range(0, len(bars) - k + 1, k):
        grp = bars[i:i + k]
        out.append(Candle(ts=grp[0].ts, open=grp[0].open,
                          high=max(c.high for c in grp),
                          low=min(c.low for c in grp), close=grp[-1].close,
                          volume=sum(c.volume for c in grp)))
    return out
