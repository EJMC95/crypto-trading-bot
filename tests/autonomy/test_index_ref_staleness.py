"""📊 Index Rider's reference-staleness guard — root cause pinned, stamp consumed.

[2026-08-04] The review found `ref_date` ~2 sessions stale with ZERO consumers
of the stamp — the shipped-but-inert class: (hl) published the date precisely
so a frozen Yahoo feed would be visible, and then nothing read it.

ROOT CAUSE, measured 4-Aug 09:34Z: Yahoo's chart API serves the MOST RECENT
COMPLETED session with a NULL close until it consolidates (SPY/QQQ/NVDA's
03-Aug bar was null on EVERY range while meta.regularMarketTime said that
session closed 03-Aug 20:00Z). `ref_closes()` drops null closes — correct, a
null is not a price — so the series ends at the last CONSOLIDATED close
(Friday, on a Tuesday). The futures refs (GC=F/CL=F/HG=F) mask the identical
hole because their ~24h sessions append a VALUED live bar dated today.

THE GUARD: the bot now consumes its own stamp — a sleeve whose reference is
older than REF_STALE_D calendar days publishes a null regime and makes no
decision (the (hk) false-FLAT rule: no entry, NO exit, catastrophic stop runs
ahead). Calibrated for the frozen-FEED class, deliberately NOT for the routine
1-2 session consolidation lag above.

The consumer is tested against a publisher-SHAPED payload (hj): the exact JSON
skeleton Yahoo returned on 4-Aug, null tail included — not a hand-written
fixture that "looks right".
"""
import ast
import datetime as dt
import io
import json
import os

import pytest

import lighter_index_bot as index_bot

pytestmark = pytest.mark.autonomy

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _yahoo_chart_payload(n_bars, null_tail=1, start_day=dt.date(2024, 1, 2)):
    """The v8/finance/chart shape as measured live 4-Aug-2026 — result[0]
    carries `timestamp` and `indicators.quote[0].close`, and the freshest
    completed session's close is null."""
    ts, closes = [], []
    day = start_day
    for i in range(n_bars):
        while day.weekday() >= 5:
            day += dt.timedelta(days=1)
        ts.append(int(dt.datetime(day.year, day.month, day.day, 13, 30,
                                  tzinfo=dt.timezone.utc).timestamp()))
        closes.append(None if i >= n_bars - null_tail else 100.0 + i * 0.1)
        day += dt.timedelta(days=1)
    return {"chart": {"result": [{
        "meta": {"regularMarketTime": ts[-1] + 6 * 3600},
        "timestamp": ts,
        "indicators": {"quote": [{"close": closes}]},
    }]}}


def test_ref_closes_dates_the_last_valued_bar_not_the_last_bar(monkeypatch):
    """The measured defect shape: a null-tailed series must (a) drop the null
    — it is not a price — and (b) stamp last_date from the last VALUED bar,
    which is what makes the staleness guard able to see the lag at all."""
    payload = _yahoo_chart_payload(index_bot.REGIME_SMA + 10, null_tail=1)
    body = json.dumps(payload).encode()
    monkeypatch.setattr("urllib.request.urlopen",
                        lambda req, timeout=20: io.BytesIO(body))
    monkeypatch.setattr(index_bot, "_ref_cache", {})

    hit = index_bot.ref_closes("SPY")
    assert hit is not None
    res = payload["chart"]["result"][0]
    assert len(hit["closes"]) == len(res["timestamp"]) - 1, "null tail kept?"
    second_last = dt.datetime.fromtimestamp(
        res["timestamp"][-2], tz=dt.timezone.utc).date().isoformat()
    assert hit["last_date"] == second_last, (
        "last_date must be the last CONSOLIDATED close — dating it off the "
        "null bar would hide the very lag the guard measures")


def test_age_math_and_calibration_in_both_directions():
    """The routine consolidation lag (measured age 4d on 4-Aug) must NOT trip
    the guard; a frozen fortnight MUST; an unparseable date is stale, never
    fresh (the sniper's ages_d rule).

    Anchor dates are SYNTHETIC (a Tuesday and its preceding Friday): the real
    measured Friday, 31-Jul, is a canonical era date and
    audit_era_date_literals owns those — the math is under test here, not
    which Friday the incident happened on."""
    now = dt.datetime(2026, 8, 11, 9, 34, tzinfo=dt.timezone.utc).timestamp()
    age = index_bot._ref_age_days
    assert age("2026-08-07", now) == 4          # Friday, seen on a Tuesday
    assert age("2026-08-11", now) == 0
    assert age("2026-07-27", now) == 15
    assert age("not-a-date", now) is None
    assert age(None, now) is None

    def stale(a):        # the guard's own expression, from main()
        return a is None or a > index_bot.REF_STALE_D

    assert not stale(age("2026-08-07", now)), "benign lag must not fire"
    assert not stale(age("2026-08-11", now))
    assert stale(age("2026-07-27", now)), "a frozen fortnight must fire"
    assert stale(age("garbage", now)), "unknown age must read stale, not fresh"


def test_the_guard_is_wired_into_main_and_published():
    """The (hl) stamp sat unconsumed because nothing WIRED it. Structural
    check (AST, not substring): main() computes _ref_age_days, compares it
    against REF_STALE_D, and the publish payload carries ref_age_d so the
    condition is machine-visible off-container."""
    tree = ast.parse(open(os.path.join(ROOT, "lighter_index_bot.py")).read())
    main_fn = next(n for n in tree.body
                   if isinstance(n, ast.FunctionDef) and n.name == "main")

    calls_age = any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                    and n.func.id == "_ref_age_days"
                    for n in ast.walk(main_fn))
    assert calls_age, "main() no longer computes the reference age"

    compares_guard = any(
        isinstance(n, ast.Compare)
        and any(isinstance(c, ast.Name) and c.id == "REF_STALE_D"
                for c in ast.walk(n))
        for n in ast.walk(main_fn))
    assert compares_guard, "main() no longer gates on REF_STALE_D"

    publishes_age = any(
        isinstance(n, ast.Dict)
        and any(isinstance(k, ast.Constant) and k.value == "ref_age_d"
                for k in n.keys if k is not None)
        for n in ast.walk(main_fn))
    assert publishes_age, "extra.ref_age_d left the publish payload"
