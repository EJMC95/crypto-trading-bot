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

v2 (2026-07-16, operator: "when any market opens or closes we are able to
allocate resources"). The clock now knows EVENTS, not just zones:
  * a real NYSE calendar — zoneinfo DST, 2026-27 holidays, 13:00-ET early
    closes. Built "because the equity-perp books (Index Rider 📊 / Stock
    Leaders 🏆) trade underlyings that only PRINT during NYSE regular hours;
    their perps trade 24/7 on a frozen index the rest of the time." Those
    facts are true; the "because" was REFUTED 17-Jul. Neither book's signal
    has ever read a perp mark — `want_position()` / `evaluate()` are pure
    functions of Yahoo dailies of the REAL market — so the frozen index
    enters no decision and the bell is not decision-relevant to them. The
    calendar STAYS (honest time math, pre-graded accurate to within one
    5-min tick, DST-correct); what it does not come with is a reason for
    anyone to obey it. See 21-Jul agenda item 11.
  * `events` / `next_event`: the next open/close of EVERY market (NYSE +
    the three crypto liquidity sessions), each with an absolute `at_utc`.
    Consumers allocate resources off `at_utc` (authoritative); the sampled
    `in_min` is display-only and ages with the payload.
  * `event_window`: true within CLOCK_EVENT_PRE_MIN before / POST_MIN after
    any open or close — the minutes when attention belongs on the market,
    so `heavy_ok` (backups, sweeps, breeding) now ALSO requires being
    outside every event window.
  * history rows only on TRANSITIONS (session change / thin flip / NYSE
    open↔closed), so `fleet-clock` history reads as an open/close event log.

ADVISORY / PUBLISH-FIRST, per doctrine: it publishes bot_state 'fleet-clock'
(+ history) for any organ to read; nothing is FORCED to obey it until a
consumer earns the wiring at a review (21-Jul agenda item 11). Fail-safe
like everything else: TTL'd, and missing tzdata degrades to sessions-only
(markets omitted, never a crash). Pure time math — no network, no ledger;
selftested offline.

Sessions (UTC, crypto trades 24/7 but liquidity/venue attention rotate):
  asia    00:00–08:00   eu   07:00–16:00   us   13:00–21:00   (overlap by design)
  off     the low-liquidity seam (21:00–24:00) — thinnest books
Weekends (Sat/Sun UTC) are flagged thin regardless — the structurally worst
execution window, and the one where a stale mark does the most damage.
"""
import os
import sys
from datetime import date, datetime, timedelta, timezone

import bot_pnl_store as store

try:
    from zoneinfo import ZoneInfo
    _NY = ZoneInfo("America/New_York")
except Exception:                                    # no tzdata → sessions-only
    _NY = None

KEY = "fleet-clock"
TTL_SEC = int(os.environ.get("CLOCK_TTL_SEC", "900"))          # 3 missed 5-min runs = stale
EVENT_PRE_MIN = float(os.environ.get("CLOCK_EVENT_PRE_MIN", "15"))
EVENT_POST_MIN = float(os.environ.get("CLOCK_EVENT_POST_MIN", "15"))

SESSION_HOURS = {"asia": (0, 8), "eu": (7, 16), "us": (13, 21)}   # UTC open/close

# ---- NYSE calendar (the market behind the SPY/QQQ/stock perps) -------------
# Full-day closures, observed dates. Extend yearly; an unknown year degrades
# to plain weekday hours with calendar_ok=False instead of guessing holidays.
NYSE_HOLIDAYS = {
    2026: {date(2026, 1, 1), date(2026, 1, 19), date(2026, 2, 16),
           date(2026, 4, 3), date(2026, 5, 25), date(2026, 6, 19),
           date(2026, 7, 3), date(2026, 9, 7), date(2026, 11, 26),
           date(2026, 12, 25)},
    2027: {date(2027, 1, 1), date(2027, 1, 18), date(2027, 2, 15),
           date(2027, 3, 26), date(2027, 5, 31), date(2027, 6, 18),
           date(2027, 7, 5), date(2027, 9, 6), date(2027, 11, 25),
           date(2027, 12, 24)},
}
NYSE_EARLY_CLOSE = {date(2026, 11, 27), date(2026, 12, 24),
                    date(2027, 11, 26)}             # 13:00 ET closes


def _iso(t):
    return t.isoformat(timespec="seconds") if t else None


def _nyse_day(d):
    """NY calendar date -> (open_utc, close_utc), or None when closed."""
    if d.weekday() >= 5 or d in NYSE_HOLIDAYS.get(d.year, set()):
        return None
    ch, cm = (13, 0) if d in NYSE_EARLY_CLOSE else (16, 0)
    o = datetime(d.year, d.month, d.day, 9, 30, tzinfo=_NY)
    c = datetime(d.year, d.month, d.day, ch, cm, tzinfo=_NY)
    return o.astimezone(timezone.utc), c.astimezone(timezone.utc)


def _nyse_state(dt):
    """UTC datetime -> (market block dict, raw [(market, kind, t_utc)]).
    (None, []) when tzdata is unavailable."""
    if _NY is None:
        return None, []
    today = dt.astimezone(_NY).date()
    cal_ok = True
    events, is_open = [], False
    for off in range(-4, 11):                       # spans any holiday cluster
        d = today + timedelta(days=off)
        if d.weekday() < 5 and d.year not in NYSE_HOLIDAYS:
            cal_ok = False
        oc = _nyse_day(d)
        if not oc:
            continue
        o, c = oc
        if o <= dt < c:
            is_open = True
        events.append((o, "open"))
        events.append((c, "close"))
    past = [e for e in events if e[0] <= dt]
    fut = [e for e in events if e[0] > dt]
    prev_t, prev_k = max(past) if past else (None, None)
    next_t, next_k = min(fut) if fut else (None, None)
    opens = [t for t, k in fut if k == "open"]
    closes = [t for t, k in fut if k == "close"]
    block = {
        "open": is_open,
        "holiday": today.weekday() < 5 and today in NYSE_HOLIDAYS.get(today.year, set()),
        "early_close": today in NYSE_EARLY_CLOSE,
        "calendar_ok": cal_ok,
        "next_open_utc": _iso(min(opens)) if opens else None,
        "next_close_utc": _iso(min(closes)) if closes else None,
        "next_event": next_k, "next_event_utc": _iso(next_t),
        "mins_to_event": round((next_t - dt).total_seconds() / 60.0, 1) if next_t else None,
        "prev_event": prev_k, "prev_event_utc": _iso(prev_t),
    }
    raw = [("nyse", k, t) for t, k in ([(prev_t, prev_k)] if prev_t else [])]
    raw += [("nyse", k, t) for t, k in fut if t in (min(opens) if opens else None,
                                                    min(closes) if closes else None)]
    return block, raw


def _daily_occurrence(dt, hour):
    """(prev, next) UTC datetimes of a fixed daily UTC hour around dt."""
    at = dt.replace(hour=hour, minute=0, second=0, microsecond=0)
    if at <= dt:
        return at, at + timedelta(days=1)
    return at - timedelta(days=1), at


def _market_events(dt, raw):
    """raw [(market, kind, t)] -> (upcoming sorted, in-window sorted).
    in_min > 0 = minutes until, < 0 = minutes since."""
    ups, win = [], []
    for market, kind, t in raw:
        in_min = (t - dt).total_seconds() / 60.0
        e = {"market": market, "event": kind, "at_utc": _iso(t),
             "in_min": round(in_min, 1)}
        if in_min > 0:
            ups.append(e)
        if -EVENT_POST_MIN <= in_min <= EVENT_PRE_MIN:
            win.append(e)
    ups.sort(key=lambda e: e["in_min"])
    win.sort(key=lambda e: abs(e["in_min"]))
    return ups[:8], win


def classify(dt):
    """Pure: a UTC datetime -> the fleet's rhythm dict. Sessions can overlap
    (real liquidity does); `sessions` lists all active, `primary` is the
    single most-representative one for display. v2 adds `markets` (NYSE),
    `events`/`next_event` (absolute open/close times across every market)
    and `event_window` — and heavy_ok now avoids event windows too."""
    h = dt.hour + dt.minute / 60.0
    wd = dt.weekday()                       # 0=Mon … 5=Sat 6=Sun
    weekend = wd >= 5
    sessions = [name for name, (o, c) in SESSION_HOURS.items() if o <= h < c]
    if not sessions:
        sessions = ["off"]
    # primary = the session whose center is nearest now (deterministic)
    centers = {"asia": 4, "eu": 11.5, "us": 17, "off": 22.5}
    primary = min(sessions, key=lambda s: abs(h - centers[s]))
    overlap = len(sessions) >= 2 and "off" not in sessions
    # thin liquidity: weekend, the off seam, or a single-session non-overlap
    # deep in the night; overlap hours are the deepest books.
    thin = weekend or primary == "off" or (not overlap and primary == "asia")

    nyse, raw = _nyse_state(dt)
    for name, (ho, hc) in SESSION_HOURS.items():
        for kind, hh in (("open", ho), ("close", hc)):
            prev_t, next_t = _daily_occurrence(dt, hh)
            raw.append((f"{name}-session", kind, prev_t))
            raw.append((f"{name}-session", kind, next_t))
    events, window_events = _market_events(dt, raw)
    event_window = bool(window_events)

    # heavy low-priority jobs (backups, big sweeps) belong in thin windows —
    # they compete with nothing that matters then. An open/close is exactly
    # when something matters: resources go to the market, not the sweep.
    heavy_ok = thin and not event_window
    return {
        "sessions": sessions, "primary": primary, "overlap": overlap,
        "weekend": weekend, "thin_liquidity": thin, "heavy_ok": heavy_ok,
        "hour_utc": round(h, 2), "weekday": wd,
        "markets": {"nyse": nyse} if nyse else {},
        "events": events, "next_event": events[0] if events else None,
        "event_window": event_window, "window_events": window_events,
        "event_pre_min": EVENT_PRE_MIN, "event_post_min": EVENT_POST_MIN,
    }


def _now():
    return datetime.now(timezone.utc)


def _transition_sig(state):
    ny = ((state or {}).get("markets") or {}).get("nyse") or {}
    return ((state or {}).get("primary"), (state or {}).get("thin_liquidity"),
            ny.get("open"))


def run_once():
    now = _now()
    r = classify(now)
    payload = {"updated": now.isoformat(timespec="seconds"), "ttl_sec": TTL_SEC, **r}
    try:
        prev = store.load_state(KEY)
    except Exception:
        prev = None
    store.save_state(KEY, payload)
    # history on TRANSITIONS only → an open/close event log, not a heartbeat
    if _transition_sig(prev) != _transition_sig(payload) and hasattr(store, "save_history"):
        try:
            store.save_history(KEY, {"updated": payload["updated"],
                                     "primary": r["primary"],
                                     "thin_liquidity": r["thin_liquidity"],
                                     "nyse_open": _transition_sig(payload)[2]})
        except Exception:
            pass
    ny = (r.get("markets") or {}).get("nyse") or {}
    ne = r.get("next_event") or {}
    print(f"[fleet-clock] {payload['updated']} session={r['primary']} "
          f"({'+'.join(r['sessions'])}) thin={r['thin_liquidity']} "
          f"heavy_ok={r['heavy_ok']} "
          f"nyse={'open' if ny.get('open') else 'closed'} "
          f"next={ne.get('market')} {ne.get('event')} in {ne.get('in_min')}m",
          flush=True)
    return payload


def _selftest():
    def dt(y, mo, d, h, mi=0):
        return datetime(y, mo, d, h, mi, tzinfo=timezone.utc)

    # ---- v1 rhythm surface (unchanged contract) ----
    assert classify(dt(2026, 7, 15, 3))["primary"] == "asia"
    assert classify(dt(2026, 7, 15, 11))["primary"] == "eu"
    assert classify(dt(2026, 7, 15, 11))["overlap"] is False     # EU alone (asia ends 08:00)
    assert classify(dt(2026, 7, 15, 7))["overlap"] is True       # asia+eu seam
    assert classify(dt(2026, 7, 15, 17))["primary"] == "us"
    off = classify(dt(2026, 7, 15, 22))
    assert off["primary"] == "off" and off["thin_liquidity"] and off["heavy_ok"]
    deep = classify(dt(2026, 7, 15, 2))
    assert deep["thin_liquidity"] and not deep["overlap"] and deep["heavy_ok"]
    mid = classify(dt(2026, 7, 15, 14))
    assert mid["overlap"] and not mid["thin_liquidity"]
    sat = classify(dt(2026, 7, 18, 14))
    assert sat["weekend"] and sat["thin_liquidity"] and sat["heavy_ok"]
    for hh in range(24):
        c = classify(dt(2026, 7, 15, hh))
        assert c["sessions"] and c["primary"] in ("asia", "eu", "us", "off")

    # ---- v2: NYSE calendar (DST both sides, holiday, early close) ----
    ny = mid["markets"]["nyse"]                       # Wed 15 Jul 14:00 UTC = 10:00 EDT
    assert ny["open"] and ny["calendar_ok"] and not ny["holiday"]
    assert ny["next_event"] == "close" and ny["next_close_utc"].startswith("2026-07-15T20:00")
    jan = classify(dt(2026, 1, 14, 14))["markets"]["nyse"]   # Wed, 09:00 EST — pre-open
    assert not jan["open"] and jan["next_open_utc"].startswith("2026-01-14T14:30")
    assert classify(dt(2026, 1, 14, 15))["markets"]["nyse"]["open"]  # 10:00 EST
    hol = classify(dt(2026, 7, 3, 15))["markets"]["nyse"]    # observed July 4th
    assert not hol["open"] and hol["holiday"]
    assert hol["next_open_utc"].startswith("2026-07-06T13:30")       # Monday reopen
    ec = classify(dt(2026, 11, 27, 17, 30))["markets"]["nyse"]  # post-Thanksgiving Fri, EST
    assert ec["open"] and ec["early_close"] and ec["next_close_utc"].startswith("2026-11-27T18:00")
    wknd = sat["markets"]["nyse"]
    assert not wknd["open"] and wknd["next_open_utc"].startswith("2026-07-20T13:30")
    assert classify(dt(2028, 6, 7, 15))["markets"]["nyse"]["calendar_ok"] is False

    # ---- v2: events + event_window + heavy_ok interplay ----
    ev = mid["events"]
    assert ev and all(e["in_min"] > 0 for e in ev)
    assert [e["in_min"] for e in ev] == sorted(e["in_min"] for e in ev)
    justopen = classify(dt(2026, 7, 15, 13, 35))      # NYSE opened 13:30 UTC
    assert justopen["event_window"] and any(
        w["market"] == "nyse" and w["event"] == "open" and w["in_min"] == -5.0
        for w in justopen["window_events"])
    preopen = classify(dt(2026, 1, 14, 14, 20))       # 10 min before winter open
    assert preopen["event_window"] and any(
        w["market"] == "nyse" and w["event"] == "open" and w["in_min"] == 10.0
        for w in preopen["window_events"])
    # thin + event window → heavy jobs must stand aside (Sat us-session open)
    satopen = classify(dt(2026, 7, 18, 13, 10))
    assert satopen["thin_liquidity"] and satopen["event_window"] and not satopen["heavy_ok"]
    # a quiet thin moment stays heavy_ok (nothing opening/closing nearby)
    assert off["event_window"] is False

    print("fleet_clock selftest OK (sessions/thin/heavy_ok + NYSE calendar "
          "DST/holiday/early-close + events/windows)")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        sys.exit(store.organ_main('fleet-clock', run_once))
