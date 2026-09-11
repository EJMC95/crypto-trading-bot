"""Test helpers and fixtures for downtrend_ensemble_bot.

DELIBERATELY NOT NAMED `conftest`. pytest manages conftest per directory, but
`from conftest import ...` resolves through sys.path -- and this repo has TWO
packages each with a top-level-importable `conftest`, so that import landed in
whichever sys.path entry came first.

MEASURED, not theorised: running both suites in ONE pytest invocation failed to
COLLECT 8 files, and CodeQL reported it as "wrong number of arguments in a
call" because it had resolved the SIBLING package's helper of the same name.
Each suite was green alone and broken together -- which is the worst shape,
because every local run looks fine.

A uniquely-named module cannot collide. `conftest.py` re-exports this one so
pytest still finds the fixtures.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from downtrend_bot.config import AppConfig                     # noqa: E402
from downtrend_bot.models import Candle, Market                # noqa: E402
from downtrend_bot.synthetic import make_market, walk  # noqa: E402

SYMS = ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"]


@pytest.fixture
def cfg(tmp_path) -> AppConfig:
    c = AppConfig()
    c.symbols = list(SYMS)
    c.benchmark_symbol = SYMS[0]
    c.runtime_dir = str(tmp_path / "runtime")
    c.reports_dir = str(tmp_path / "reports")
    c.data_dir = str(tmp_path / "data")
    c.state_db = str(tmp_path / "runtime" / "state.sqlite")
    os.makedirs(c.runtime_dir, exist_ok=True)
    return c


@pytest.fixture
def markets() -> dict[str, Market]:
    return {s: make_market(s) for s in SYMS}


def bars(n: int, *, drift: float, vol: float = 0.004, seed: int = 3,
         start: float = 100.0, tf: str = "1h", t0: float = 1_700_000_000.0):
    return walk(bars=n, start=start, drift_per_bar=drift, vol=vol, seed=seed,
                t0=t0, tf=tf)


def falling(n: int = 400, **kw) -> list[Candle]:
    return bars(n, drift=-0.004, **kw)


def rising(n: int = 400, **kw) -> list[Candle]:
    return bars(n, drift=+0.004, **kw)


def flat(n: int = 400, **kw) -> list[Candle]:
    return bars(n, drift=0.0, **kw)


def tape(symbols=SYMS, *, bars_1h: int = 500, seed: int = 5,
         downtrend: bool = True):
    """A coherent 15m/1h/4h tape, aggregated so the timeframes agree."""
    from downtrend_bot.synthetic import tapes
    return tapes(symbols, bars_1h=bars_1h, seed=seed, downtrend=downtrend)


def breakdown_tape(n: int = 300, *, level: float = 100.0,
                   t0: float = 1_700_000_000.0) -> list[Candle]:
    """A HAND-BUILT tape containing the setup BY CONSTRUCTION: a long clean
    range, a decisive closed break below it, then a retest that rejects.

    THE BAR POSITIONS ARE THE POINT and getting them wrong is how the first
    version of this fixture silently proved nothing. The component takes its
    level from the `structure_window` bars ENDING at `i - BREAK_LOOKBACK - 1`,
    and searches `[i - BREAK_LOOKBACK, i)` for the break. So the break must sit
    inside the last `BREAK_LOOKBACK` bars while every bar of the range window
    is still clean -- put the break one bar too early and the range floor
    absorbs it, the level drops to the broken price, and the control tape tests
    nothing while looking perfectly reasonable."""
    out: list[Candle] = []
    body = n - 5                      # break + 3 drift + retest = the last 5
    for i in range(body):
        out.append(Candle(t0 + i * 3600, level + 2, level + 4, level, level + 2,
                          1000.0))
    out.append(Candle(t0 + body * 3600, level + 2, level + 2, level - 3.5,
                      level - 3, 4000.0))                     # the break
    for k in range(3):                                        # hold below
        out.append(Candle(t0 + (body + 1 + k) * 3600, level - 3, level - 2,
                          level - 4, level - 3, 2000.0))
    # The retest wicks back INTO the level and closes rejected in the lower
    # half -- and NEAR it, because the component deliberately scores nothing
    # once price has already run more than `max_entry_distance_atr` away.
    out.append(Candle(t0 + (body + 4) * 3600, level - 2.5, level + 0.5,
                      level - 3.0, level - 2.2, 3000.0))
    return out


def overrun_pivot_tape(n: int = 300, t0: float = 1_700_000_000.0):
    """A tape whose last CONFIRMED swing low sits ABOVE the current close.

    This is the ordinary shape of a market that keeps falling: a pivot forms,
    price runs straight through it, and no new pivot is confirmed yet. Taking
    that pivot as a long's invalidation level puts the stop ABOVE the entry --
    a trade stopped on its own fill, sized off an `abs(entry - stop)` that
    looks perfectly healthy."""
    out: list[Candle] = []
    px = 200.0
    for i in range(n - 40):                      # a long, gently rising base
        px += 0.05
        out.append(Candle(t0 + i * 3600, px, px + 0.5, px - 0.5, px, 1000.0))
    # a clean confirmed swing low, then a straight run far below it
    for k, d in enumerate((-1.0, -2.0, -1.0, +1.0, +2.0)):
        px += d
        out.append(Candle(t0 + (n - 40 + k) * 3600, px, px + 0.4, px - 0.4, px,
                          1000.0))
    for k in range(35):                          # runs through the pivot
        px -= 1.5
        out.append(Candle(t0 + (n - 35 + k) * 3600, px + 1.5, px + 1.6,
                          px - 0.2, px, 1200.0))
    return out


def read_text(path) -> str:
    """`open(p).read()` leaks the handle on any runtime that is not CPython
    refcounting, and CodeQL flags every instance. One helper, no leaks."""
    with open(path) as fh:
        return fh.read()
