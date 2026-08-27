#!/usr/bin/env python3
"""THE VENUE TAPE, FETCHED ONCE. A durable on-disk cache of CLOSED candles.

**Eamon, 27-Aug: *"I think we record things far too slowly and it impairs our
judgement."*** Measured the same day: **39 study scripts fetch venue candles
and there is no shared cache**, against a venue that throttles at ~21
requests/min ([[lighter-tape-fetch-throttle]]). A 400-day hourly pull for 21
symbols is ~190 requests — about nine minutes — and every study pays it again
from scratch. I paid it TWICE in one session.

The cost is not the wall-clock. It is that a measurement which takes ten
minutes does not get re-run, so a number gets quoted from memory instead of
re-derived — which is exactly how a study ends up reasoning from a stale or
mis-specified window.

WHY CACHING HERE IS CORRECTNESS-NEUTRAL, and it is measured rather than
assumed: **historical bars on this venue do not revise.** `(nu)` re-fetched
1,500 bars while chasing a founding number and found **zero differences**. So
a bar whose period has CLOSED is immutable, and serving it from disk is the
same answer the venue would give.

THE ONE RULE THAT MAKES IT SAFE: **only closed bars are ever cached.** The bar
covering `now` is still forming — its close moves with every trade — so it is
never written and never served. `_closed_before()` is the single owner of that
boundary. Without it a study would silently read a partial bar as a settled
one, which is the (ml) entry-bar class in a new costume.

USAGE — a drop-in for the `fetch_candles(market_id, start, end, resolution)`
shape the studies already share:

    from tape_cache import cached_candles
    bars = cached_candles(mid, start_ts, end_ts, "1h")     # {ts: (o,h,l,c,v)}
    print(stats())        # {'hits': 4103, 'fetched': 97, 'requests': 1}

`fetcher=` injects the network call, defaulting to the fetcher the studies
already reuse — so THIS FILE OWNS NO FETCH RULE. A second copy of the paging
logic would be a second rule, and this fleet has paid for that shape before.

FAIL-SAFE, in the only direction that is safe for a cache: any doubt about the
cache — unreadable, corrupt, wrong schema, unwritable directory — degrades to a
LIVE FETCH, never to an empty result. A cache that returns `{}` on a bad read
would make every study silently measure nothing, which is the
check-that-inspects-nothing failure with a performance excuse.

    python3 scripts/tape_cache.py --selftest
    python3 scripts/tape_cache.py --stats        # what is on disk
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

#: Gitignored (see `.gitignore`'s backtest-cache block, the same idiom as
#: `scripts/.funding_cache.json`). Kept beside the studies that use it.
CACHE_DIR = os.environ.get("TAPE_CACHE_DIR", os.path.join(HERE, ".tape_cache"))

#: Bar width in seconds per resolution — the venue's own grid.
STEP = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "1d": 86400}

#: Cache file schema. Bumping it invalidates every file rather than risking a
#: silent misread of an older shape.
SCHEMA = 1

_STATS = {"hits": 0, "fetched": 0, "requests": 0, "files": 0, "errors": 0}


def stats():
    return dict(_STATS)


def reset_stats():
    for k in _STATS:
        _STATS[k] = 0


def _closed_before(resolution, now=None):
    """Newest bar-open that is definitely CLOSED, i.e. safe to cache.

    THE LOAD-BEARING LINE OF THIS MODULE. The bar containing `now` is still
    forming and its close will change, so the newest cacheable open is the
    start of the PREVIOUS bar. Off-by-one here does not error — it silently
    freezes a partial bar into every future study, which is the worst kind of
    defect this repo names: wrong, quiet, and durable.
    """
    step = STEP[resolution]
    n = int(time.time() if now is None else now)
    return (n // step) * step - step


def _path(market_id, resolution):
    return os.path.join(CACHE_DIR, f"{int(market_id)}_{resolution}.json")


def _read(market_id, resolution):
    """{ts: tuple} from disk. Any doubt -> {} (a miss), never an exception."""
    try:
        with open(_path(market_id, resolution), encoding="utf-8") as fh:
            blob = json.load(fh)
        if not isinstance(blob, dict) or blob.get("schema") != SCHEMA:
            return {}
        bars = blob.get("bars") or {}
        out = {}
        for t, v in bars.items():
            try:
                if len(v) == 5:
                    out[int(t)] = tuple(float(x) for x in v)
            except (TypeError, ValueError):
                continue
        return out
    except FileNotFoundError:
        return {}
    except Exception:                                       # noqa: BLE001
        _STATS["errors"] += 1
        return {}


def _write(market_id, resolution, bars):
    """Atomic replace. A failed write is a WARNING, never an error: the caller
    already has correct data in memory, and a cache that raises would make the
    fast path less reliable than no cache at all."""
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        p = _path(market_id, resolution)
        tmp = f"{p}.tmp{os.getpid()}"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"schema": SCHEMA, "resolution": resolution,
                       "market_id": int(market_id),
                       "bars": {str(t): list(v) for t, v in bars.items()}}, fh)
        os.replace(tmp, p)
        return True
    except Exception:                                       # noqa: BLE001
        _STATS["errors"] += 1
        return False


def _default_fetcher():
    """The fetcher the studies already share — imported, never re-implemented.

    Paging the venue's 500-bar cap correctly is a real rule with real traps
    (the oldest-timestamp loop guard, the `count_back` argument); a second copy
    here could disagree with what every study has already measured against.
    """
    import importlib.util
    src = os.path.join(HERE, "study_sniper_exit_shape_2026-08-20.py")
    spec = importlib.util.spec_from_file_location("_tc_fetch", src)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.fetch_candles


def cached_candles(market_id, start_ts, end_ts, resolution="1h", fetcher=None,
                   now=None):
    """{bar_ts: (o,h,l,c,quote_vol)} over [start, end], cache-first.

    Closed bars already on disk are served without a request. Anything missing
    is fetched ONCE, in a single span covering the gap, and the closed part of
    the result is written back.
    """
    if resolution not in STEP:
        raise ValueError(f"unknown resolution {resolution!r}")
    step = STEP[resolution]
    start_ts, end_ts = int(start_ts), int(end_ts)
    safe_to = _closed_before(resolution, now)

    have = _read(market_id, resolution)
    if have:
        _STATS["files"] += 1

    # What the caller asked for that we can serve from disk.
    want_lo = (start_ts // step) * step
    want_hi = min(end_ts, safe_to)
    served = {t: v for t, v in have.items() if want_lo <= t <= want_hi}

    # The gap: everything in the CLOSED window we do not already hold. A
    # contiguous span is fetched rather than per-bar requests — the venue pages
    # 500 at a time and one wide call is far cheaper than many narrow ones.
    missing = [t for t in range(want_lo, want_hi + 1, step) if t not in have]
    fetched = {}
    if missing or end_ts > safe_to:
        lo = min(missing) if missing else max(want_hi + step, start_ts)
        # The still-forming tail is ALWAYS fetched live: it is never cached, so
        # a caller asking for `now` still gets the venue's current answer.
        hi = end_ts
        fn = fetcher or _default_fetcher()
        _STATS["requests"] += 1
        fetched = fn(market_id, lo, hi, resolution) or {}
        _STATS["fetched"] += len(fetched)
        closed_new = {t: v for t, v in fetched.items() if t <= safe_to}
        if closed_new:
            merged = dict(have)
            merged.update(closed_new)
            _write(market_id, resolution, merged)

    _STATS["hits"] += len(served)
    out = dict(served)
    out.update({t: v for t, v in fetched.items()
                if start_ts <= t <= end_ts})
    return {t: v for t, v in out.items() if start_ts <= t <= end_ts}


def disk_stats():
    rows = []
    try:
        names = sorted(os.listdir(CACHE_DIR))
    except OSError:
        return rows
    for n in names:
        if not n.endswith(".json"):
            continue
        p = os.path.join(CACHE_DIR, n)
        try:
            blob = json.load(open(p, encoding="utf-8"))
            rows.append((n, len(blob.get("bars") or {}),
                         os.path.getsize(p)))
        except Exception:                                   # noqa: BLE001
            rows.append((n, -1, os.path.getsize(p)))
    return rows


def selftest():
    import shutil
    import tempfile
    ok = True
    global CACHE_DIR
    tmp = tempfile.mkdtemp()
    old = CACHE_DIR
    CACHE_DIR = tmp
    try:
        NOW = 1_800_000_000
        step = 3600
        safe = _closed_before("1h", NOW)

        def _fake(calls):
            def f(mid, lo, hi, res):
                calls.append((lo, hi))
                out = {}
                t = (int(lo) // step) * step
                while t <= hi:
                    out[t] = (1.0, 2.0, 0.5, 1.5, 10.0)
                    t += step
                return out
            return f

        # 1. cold -> one request; warm -> ZERO requests.
        calls = []
        reset_stats()
        lo, hi = safe - 20 * step, safe
        a = cached_candles(7, lo, hi, "1h", fetcher=_fake(calls), now=NOW)
        if len(calls) != 1 or not a:
            print(f"  FAIL cold fetch: calls={len(calls)} bars={len(a)}")
            ok = False
        else:
            print(f"  ok   cold fetch: 1 request, {len(a)} bars")
        calls2 = []
        b = cached_candles(7, lo, hi, "1h", fetcher=_fake(calls2), now=NOW)
        if calls2 or b != a:
            print(f"  FAIL warm read: calls={len(calls2)} same={b == a}")
            ok = False
        else:
            print("  ok   warm read: 0 requests, identical bars")

        # 2. THE LOAD-BEARING RULE: the forming bar is never cached.
        forming = (NOW // step) * step
        calls3 = []
        cached_candles(7, lo, forming + step, "1h", fetcher=_fake(calls3), now=NOW)
        on_disk = _read(7, "1h")
        if forming in on_disk:
            print(f"  FAIL the FORMING bar {forming} was cached")
            ok = False
        else:
            print("  ok   the forming bar is never written to disk")
        if not calls3:
            print("  FAIL a request spanning `now` must still hit the venue")
            ok = False
        else:
            print("  ok   a request spanning `now` still fetches live")

        # 3. A corrupt cache degrades to a FETCH, never to an empty result.
        with open(_path(7, "1h"), "w") as fh:
            fh.write("{not json")
        calls4 = []
        c = cached_candles(7, lo, hi, "1h", fetcher=_fake(calls4), now=NOW)
        if not c or not calls4:
            print(f"  FAIL corrupt cache: bars={len(c)} calls={len(calls4)}")
            ok = False
        else:
            print("  ok   a corrupt cache re-fetches instead of returning {}")

        # 4. A wrong schema is a miss, not a misread.
        _write(7, "1h", {safe: (1, 2, 3, 4, 5)})
        blob = json.load(open(_path(7, "1h")))
        blob["schema"] = SCHEMA + 99
        json.dump(blob, open(_path(7, "1h"), "w"))
        if _read(7, "1h") != {}:
            print("  FAIL a future schema was read anyway")
            ok = False
        else:
            print("  ok   an unknown schema is a miss")

        # 5. The window is respected exactly — no bar outside [start, end].
        calls5 = []
        d = cached_candles(7, lo + 5 * step, lo + 8 * step, "1h",
                           fetcher=_fake(calls5), now=NOW)
        if d and (min(d) < lo + 5 * step or max(d) > lo + 8 * step):
            print(f"  FAIL window leak: {min(d)}..{max(d)}")
            ok = False
        else:
            print("  ok   returned bars sit inside the requested window")
    finally:
        CACHE_DIR = old
        shutil.rmtree(tmp, ignore_errors=True)
    print("tape_cache selftest:", "OK" if ok else "FAILED")
    return 0 if ok else 1


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--stats", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    rows = disk_stats()
    total = sum(r[1] for r in rows if r[1] > 0)
    size = sum(r[2] for r in rows)
    print(f"tape_cache: {len(rows)} file(s), {total:,} closed bars, "
          f"{size/1e6:.1f} MB in {CACHE_DIR}")
    for n, bars, sz in rows[:20]:
        print(f"  {n:<24}{bars:>8,} bars{sz/1e3:>10.0f} kB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
