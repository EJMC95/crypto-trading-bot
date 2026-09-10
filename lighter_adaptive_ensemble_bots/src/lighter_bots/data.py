"""Candle acquisition, caching and the incomplete-bar rule.

THE ONE RULE THAT MATTERS: an OPEN bar is never handed to a signal. Lighter's
`/api/v1/candles` returns the forming bar alongside closed ones, and using it
is the cheapest possible look-ahead -- the bar's high/low keep growing after
you have decided. `closed_bars()` is the only supported way to get a series,
and it drops the forming bar by TIMESTAMP arithmetic rather than by trusting
any flag the venue may or may not send.

Freshness is separate from completeness: a series can be all-closed and still
be hours stale. `staleness_s` answers that, and a stale feed is a
DATA_UNRELIABLE regime input, not a warning to ignore.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Iterable, Sequence

from .logging_setup import get
from .models import Candle

log = get("data")

TF_SECONDS = {"1m": 60, "5m": 300, "15m": 900, "30m": 1800, "1h": 3600,
              "4h": 14400, "1d": 86400}

#: Lighter's candle page size.
PAGE = 500


def tf_seconds(tf: str) -> int:
    if tf not in TF_SECONDS:
        raise ValueError(f"unsupported timeframe {tf!r}; "
                         f"known: {sorted(TF_SECONDS)}")
    return TF_SECONDS[tf]


#: Transient venue responses. 405 is the one that surprises people: Lighter
#: answers a rate-limited GET with "405 Not Allowed", which reads like a
#: permanent method error and is not -- the same URL succeeds seconds later.
#: Measured while pulling 300 days of 15m tape across eight markets.
_RETRYABLE = (405, 408, 429, 500, 502, 503, 504)


def _http_json(url: str, timeout: int = 30, tries: int = 5,
               backoff: float = 1.5) -> dict[str, Any]:
    """GET with exponential backoff on TRANSIENT failures only.

    This retries READS. It is deliberately not used for anything signed: a
    blindly retried signed order can execute twice, which is why
    `lighter_adapter` keeps its own no-retry path for writes."""
    last: Exception | None = None
    for attempt in range(max(1, tries)):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "lighter-bots/0.1"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code not in _RETRYABLE:
                raise
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last = exc
        if attempt + 1 < tries:
            delay = backoff * (2 ** attempt)
            log.warning("retrying %s in %.1fs (%s)", url.split("?")[0], delay,
                        last)
            time.sleep(delay)
    raise last if last else RuntimeError(f"GET failed: {url}")


def closed_bars(candles: Sequence[Candle], tf: str,
                now_s: float | None = None) -> list[Candle]:
    """Drop any bar whose close time has not passed. Derived from the bar's
    own open timestamp + the timeframe, so it does not depend on a venue flag."""
    sec = tf_seconds(tf)
    now_s = time.time() if now_s is None else now_s
    return [c for c in candles if c.ts + sec <= now_s]


def staleness_s(candles: Sequence[Candle], tf: str,
                now_s: float | None = None) -> float:
    """Seconds since the last CLOSED bar should have closed. 0 means current;
    a value >= one bar means the feed has missed a print."""
    if not candles:
        return float("inf")
    now_s = time.time() if now_s is None else now_s
    sec = tf_seconds(tf)
    return max(0.0, now_s - (candles[-1].ts + sec))


def is_fresh(candles: Sequence[Candle], tf: str, tolerance_bars: float = 2.0,
             now_s: float | None = None) -> bool:
    return staleness_s(candles, tf, now_s) <= tolerance_bars * tf_seconds(tf)


class CandleSource:
    """Lighter candles with an on-disk cache.

    The cache is keyed (symbol, timeframe) and stores CLOSED bars only, so a
    cached series can never re-introduce a forming bar on a later run."""

    def __init__(self, base_url: str, data_dir: str, sleep_s: float = 0.35):
        self.base_url = base_url.rstrip("/")
        self.raw = os.path.join(data_dir, "raw")
        os.makedirs(self.raw, exist_ok=True)
        self.sleep_s = sleep_s

    def _path(self, symbol: str, tf: str) -> str:
        return os.path.join(self.raw, f"{symbol}_{tf}.json")

    def load_cached(self, symbol: str, tf: str) -> list[Candle]:
        p = self._path(symbol, tf)
        if not os.path.exists(p):
            return []
        with open(p) as fh:
            rows = json.load(fh)
        return [Candle(*row) for row in rows]

    def save(self, symbol: str, tf: str, candles: Iterable[Candle]) -> None:
        rows = [[c.ts, c.open, c.high, c.low, c.close, c.volume, True]
                for c in candles]
        with open(self._path(symbol, tf), "w") as fh:
            json.dump(rows, fh)

    def fetch(self, market_id: int, tf: str, pages: int = 4,
              now_s: float | None = None) -> list[Candle]:
        """Page backwards from now. Returns CLOSED bars, oldest first."""
        sec = tf_seconds(tf)
        end = int(time.time() if now_s is None else now_s)
        rows: dict[int, Candle] = {}
        for _ in range(max(1, pages)):
            q = urllib.parse.urlencode({
                "market_id": market_id, "resolution": tf,
                "start_timestamp": end - PAGE * sec,
                "end_timestamp": end, "count_back": PAGE})
            doc = _http_json(f"{self.base_url}/api/v1/candles?{q}")
            page = (doc or {}).get("c") or []
            if not page:
                break
            for c in page:
                ts = int(c["t"]) // 1000
                rows[ts] = Candle(ts, float(c["o"]), float(c["h"]),
                                  float(c["l"]), float(c["c"]),
                                  float(c.get("v") or 0.0))
            oldest = min(int(c["t"]) // 1000 for c in page)
            if len(page) < PAGE * 0.8:
                break
            end = oldest - 1
            time.sleep(self.sleep_s)
        series = [rows[t] for t in sorted(rows)]
        return closed_bars(series, tf, now_s)

    def get(self, symbol: str, market_id: int, tf: str, pages: int = 4,
            use_cache: bool = True, now_s: float | None = None) -> list[Candle]:
        if use_cache:
            cached = self.load_cached(symbol, tf)
            if cached and is_fresh(cached, tf, tolerance_bars=1.0, now_s=now_s):
                return cached
        series = self.fetch(market_id, tf, pages=pages, now_s=now_s)
        if series:
            self.save(symbol, tf, series)
        return series


def to_columns(candles: Sequence[Candle]) -> dict[str, list[float]]:
    return {"t": [c.ts for c in candles], "o": [c.open for c in candles],
            "h": [c.high for c in candles], "l": [c.low for c in candles],
            "c": [c.close for c in candles], "v": [c.volume for c in candles]}


def resample_marker(candles: Sequence[Candle], tf_from: str, tf_to: str
                    ) -> list[int]:
    """Indices in `candles` (tf_from) where a tf_to bar CLOSES. Used to align
    a 15m execution tape to 1h/4h decisions without look-ahead."""
    a, b = tf_seconds(tf_from), tf_seconds(tf_to)
    if b % a:
        raise ValueError(f"{tf_to} is not a whole multiple of {tf_from}")
    return [i for i, c in enumerate(candles) if (c.ts + a) % b == 0]
