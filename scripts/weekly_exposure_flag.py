#!/usr/bin/env python3
"""The weekly scoreboard's exposure flag — read from the ENFORCER, not counted.

    python3 scripts/weekly_exposure_flag.py --bus bus.json   # prints the flag, or nothing
    python3 scripts/weekly_exposure_flag.py --selftest

[2026-08-17 (pp)] WHY THIS EXISTS. `fleet-weekly-assessment.yml` used to flag

    EXPOSURE BREACH - 40 open vs budget 20

by comparing `sum(open_trades)` across every row of `/pnl.json` against a
hardcoded `EXPOSURE_BUDGET: '20'`. **It fired every week it was measured** — 58
vs 20 on 09-Aug, 40 vs 20 on 16-Aug — while the fleet sat at long 11/20 with
`fleet_risk` publishing a GREEN light.

The comparison was never of like with like. That budget is **long-only**: the
veto is `long_positions >= long_budget`, against NEW LONG entries. `total_open`
counts shorts and, overwhelmingly, **delta-neutral funding legs** — ⚖️
Counterweight alone holds 10 (= 5 pairs), which are not directional exposure at
all. So the flag measured "how many positions does the fleet hold", called it a
breach, and was wrong every time.

That is the `(gl)` cry-wolf shape sitting in the artifact the Monday verdict is
built from, and the cost is not the false alarm: it is that a REAL breach
arrives looking identical to two months of noise.

**THE NUMBER IS NOT RE-DERIVED HERE.** `fleet_risk` owns the rule, so this reads
its published pair and applies its comparison — a second copy of a rule is a
second rule ((hj)). Note the payload carries two different counts on purpose
((iv)): `long_positions` is the BUDGET cohort the veto uses, `exposure.long_n`
is the symbol-harvested population, and `sym_over` is non-zero exactly when they
describe different sets. **This uses the pair the veto uses.**

**I1, LIVENESS BEFORE SEMANTICS.** A `fleet_risk` payload that stopped updating
is byte-identical to a healthy one apart from its timestamp, so the age is
checked before the numbers are believed. Dark, unparseable, field-less and stale
each return a VISIBLE `EXPOSURE UNKNOWN` string — never silence. Silence here
means "checked, nothing to report", and it must never also mean "nobody
asked" ((kw)).
"""
from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import sys

UNKNOWN = "EXPOSURE UNKNOWN"


def exposure_flag(bus, now=None):
    """-> flag string, or None when the fleet is verifiably within budget.

    `bus` is the parsed /bus.json mapping, or None when it could not be read.
    Pure, so the selftest drives every branch without a network or a clock.
    """
    now = now or datetime.datetime.now(datetime.timezone.utc)
    if bus is None:
        return f"{UNKNOWN} - bus unreachable, long-budget not checked"
    if not isinstance(bus, dict):
        return f"{UNKNOWN} - bus payload is not an object"

    fr = bus.get("fleet_risk")
    if not isinstance(fr, dict):
        return f"{UNKNOWN} - bus carries no fleet_risk key"

    n, lim = fr.get("long_positions"), fr.get("long_budget")
    # bool is an int subclass; a True here would sail through and compare as 1
    if isinstance(n, bool) or isinstance(lim, bool) \
            or not isinstance(n, (int, float)) or not isinstance(lim, (int, float)):
        return f"{UNKNOWN} - fleet_risk published no long_positions/long_budget"

    try:
        stamp = datetime.datetime.fromisoformat(str(fr.get("updated")))
    except (TypeError, ValueError):
        return f"{UNKNOWN} - fleet_risk carries no readable `updated`"
    if stamp.tzinfo is None:                      # naive stamps are UTC here
        stamp = stamp.replace(tzinfo=datetime.timezone.utc)
    age = (now - stamp).total_seconds()

    ttl = fr.get("ttl_sec")
    if isinstance(ttl, (int, float)) and not isinstance(ttl, bool) and age > ttl:
        return (f"{UNKNOWN} - fleet_risk stale ({age / 3600:.1f}h vs ttl "
                f"{ttl / 3600:.1f}h); long was {int(n)}/{int(lim)} when it stopped")

    if n > lim:
        return (f"EXPOSURE BREACH - long {int(n)}/{int(lim)} "
                f"(fleet_risk, {age / 60:.0f}m old)")
    return None


def _load(path):
    p = pathlib.Path(path)
    if not p.exists() or p.stat().st_size == 0:
        return None
    try:
        return json.loads(p.read_text())
    except Exception:                              # noqa: BLE001 — dark is an answer
        return "unparseable"


def _selftest():
    fresh = "2026-08-17T00:00:00+00:00"
    now = datetime.datetime(2026, 8, 17, 0, 5, tzinfo=datetime.timezone.utc)

    def bus(**kw):
        fr = {"long_positions": 11, "long_budget": 20,
              "updated": fresh, "ttl_sec": 900}
        fr.update(kw)
        return {"fleet_risk": fr}

    # within budget -> SILENCE (the only silent branch)
    assert exposure_flag(bus(), now) is None

    # a real breach still fires, and names the enforcer's own pair
    f = exposure_flag(bus(long_positions=21), now)
    assert f and f.startswith("EXPOSURE BREACH") and "21/20" in f, f

    # at the budget is NOT over it
    assert exposure_flag(bus(long_positions=20), now) is None

    # THE DEFECT THIS FILE EXISTS FOR: a fleet holding 40 positions of which 11
    # are long is WITHIN a long budget of 20, and must not flag.
    assert exposure_flag(bus(long_positions=11), now) is None

    # every dark path is VISIBLE, and none of them is silence
    for arg in (None, [], "nope", 42):
        assert (exposure_flag(arg, now) or "").startswith(UNKNOWN), arg
    assert (exposure_flag({}, now) or "").startswith(UNKNOWN)
    assert (exposure_flag({"fleet_risk": None}, now) or "").startswith(UNKNOWN)
    for bad in ({"long_positions": None}, {"long_budget": "20"},
                {"long_positions": True}, {"long_budget": False}):
        assert (exposure_flag(bus(**bad), now) or "").startswith(UNKNOWN), bad

    # I1: a stale payload is UNKNOWN even though its numbers look clean
    stale = exposure_flag(bus(updated="2026-08-16T00:00:00+00:00"), now)
    assert stale and stale.startswith(UNKNOWN) and "stale" in stale, stale
    # ...and a stale payload that was ALSO over budget still says UNKNOWN,
    # because an unlive number cannot support either verdict
    both = exposure_flag(bus(updated="2026-08-16T00:00:00+00:00",
                             long_positions=99), now)
    assert both and both.startswith(UNKNOWN), both

    # an unreadable stamp is UNKNOWN, not a crash
    for s in (None, "", "not-a-date", 12345):
        assert (exposure_flag(bus(updated=s), now) or "").startswith(UNKNOWN), s

    # a naive stamp is read as UTC rather than exploding
    assert exposure_flag(bus(updated="2026-08-17T00:00:00"), now) is None

    # no ttl published -> age cannot condemn it; the numbers still speak
    assert exposure_flag(bus(ttl_sec=None), now) is None
    assert (exposure_flag(bus(ttl_sec=None, long_positions=21), now)
            or "").startswith("EXPOSURE BREACH")

    print("weekly_exposure_flag selftest OK "
          "(clean/breach/at-budget/dark x7/stale/naive/no-ttl)")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bus", default="bus.json")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return _selftest()
    raw = _load(a.bus)
    flag = exposure_flag(None if raw == "unparseable" else raw)
    if raw == "unparseable":
        flag = f"{UNKNOWN} - bus unparseable"
    if flag:
        print(flag)
    return 0


if __name__ == "__main__":
    sys.exit(main())
