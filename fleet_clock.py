#!/usr/bin/env python3
"""
fleet_clock.py — 🕐 the fleet's CIRCADIAN organ (coordinated sense of time).

WHY (2026-07-15, operator's organism framing: "what organ coordinates
rhythms — when to be aggressive, when to rest, when to run heavy jobs").
Timing was scattered across run_all.sh sleeps and cron with no shared sense
of WHEN it is. This organ is the single source of the fleet's rhythm: one
place that knows the trading session, whether liquidity is thin (weekend /
off-hours — when execution is worst), and whether now is a good time for
heavy low-priority jobs.

ADVISORY / PUBLISH-FIRST, per doctrine: it publishes bot_state 'fleet-clock'
(+ history) for any organ to read; nothing is FORCED to obey it until a
consumer earns the wiring at a review. Fail-safe like everything else
(TTL'd). Pure time math — no network, no ledger; selftested offline.

Sessions (UTC, crypto trades 24/7 but liquidity/venue attention rotate):
  asia    00:00–08:00   eu   07:00–16:00   us   13:00–21:00   (overlap by design)
  off     the low-liquidity seam (21:00–24:00) — thinnest books
Weekends (Sat/Sun UTC) are flagged thin regardless — the structurally worst
execution window, and the one where a stale mark does the most damage.
"""
import os
import sys
from datetime import datetime, timezone

import bot_pnl_store as store

KEY = "fleet-clock"
TTL_SEC = int(os.environ.get("CLOCK_TTL_SEC", "1800"))    # 30 min


def classify(dt):
    """Pure: a UTC datetime -> the fleet's rhythm dict. Sessions can overlap
    (real liquidity does); `sessions` lists all active, `primary` is the
    single most-representative one for display."""
    h = dt.hour + dt.minute / 60.0
    wd = dt.weekday()                       # 0=Mon … 5=Sat 6=Sun
    weekend = wd >= 5
    sessions = []
    if 0 <= h < 8:
        sessions.append("asia")
    if 7 <= h < 16:
        sessions.append("eu")
    if 13 <= h < 21:
        sessions.append("us")
    if not sessions:
        sessions.append("off")
    # primary = the session whose center is nearest now (deterministic)
    centers = {"asia": 4, "eu": 11.5, "us": 17, "off": 22.5}
    primary = min(sessions, key=lambda s: abs(h - centers[s]))
    overlap = len(sessions) >= 2 and "off" not in sessions
    # thin liquidity: weekend, the off seam, or a single-session non-overlap
    # deep in the night; overlap hours are the deepest books.
    thin = weekend or primary == "off" or (not overlap and primary == "asia")
    # heavy low-priority jobs (backups, big sweeps) belong in thin windows —
    # they compete with nothing that matters then.
    heavy_ok = thin
    return {
        "sessions": sessions, "primary": primary, "overlap": overlap,
        "weekend": weekend, "thin_liquidity": thin, "heavy_ok": heavy_ok,
        "hour_utc": round(h, 2), "weekday": wd,
    }


def _now():
    return datetime.now(timezone.utc)


def run_once():
    now = _now()
    r = classify(now)
    payload = {"updated": now.isoformat(timespec="seconds"), "ttl_sec": TTL_SEC, **r}
    store.save_state(KEY, payload)
    if hasattr(store, "save_history"):
        try:
            store.save_history(KEY, {"updated": payload["updated"],
                                     "primary": r["primary"],
                                     "thin_liquidity": r["thin_liquidity"]})
        except Exception:
            pass
    print(f"[fleet-clock] {payload['updated']} session={r['primary']} "
          f"({'+'.join(r['sessions'])}) overlap={r['overlap']} "
          f"thin={r['thin_liquidity']} heavy_ok={r['heavy_ok']}", flush=True)
    return payload


def _selftest():
    def dt(y, mo, d, h):
        return datetime(y, mo, d, h, 0, tzinfo=timezone.utc)

    # a Wednesday across the day
    assert classify(dt(2026, 7, 15, 3))["primary"] == "asia"
    assert classify(dt(2026, 7, 15, 11))["primary"] == "eu"
    assert classify(dt(2026, 7, 15, 11))["overlap"] is False     # EU alone (asia ends 08:00)
    assert classify(dt(2026, 7, 15, 7))["overlap"] is True       # asia+eu seam
    assert classify(dt(2026, 7, 15, 17))["primary"] == "us"
    off = classify(dt(2026, 7, 15, 22))
    assert off["primary"] == "off" and off["thin_liquidity"] and off["heavy_ok"]
    # deep-Asia single session (early, no eu overlap) reads thin
    deep = classify(dt(2026, 7, 15, 2))
    assert deep["thin_liquidity"] and not deep["overlap"]
    # eu/us overlap midday is the deep-book window (not thin)
    mid = classify(dt(2026, 7, 15, 14))
    assert mid["overlap"] and not mid["thin_liquidity"]
    # Saturday is thin whatever the hour
    sat = classify(dt(2026, 7, 18, 14))
    assert sat["weekend"] and sat["thin_liquidity"] and sat["heavy_ok"]
    # every hour classifies without error and yields >=1 session
    for hh in range(24):
        c = classify(dt(2026, 7, 15, hh))
        assert c["sessions"] and c["primary"] in ("asia", "eu", "us", "off")
    print("fleet_clock selftest OK (sessions, overlap, thin/weekend, heavy_ok)")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        run_once()
