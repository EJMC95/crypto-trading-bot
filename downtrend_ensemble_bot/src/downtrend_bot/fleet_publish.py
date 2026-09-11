"""OPTIONAL publisher to the fleet's `bot_pnl` dashboard table.

THE POINT OF THIS FILE IS THAT THE PACKAGE DOES NOT DEPEND ON IT. `bot_pnl_store`
lives in the surrounding repo, needs a `DATABASE_URL`, and is absent from a
standalone checkout -- so it is imported LAZILY and every failure to find it is
a silent no-op. The 274 tests run with no database and no fleet.

WHY PUBLISH AT ALL: a dashboard row for a bot that publishes nothing is a
permanent "no data yet" ghost card, and the dashboard's own source records that
exact defect ("a retirement must not leave a placeholder haunting the staged
sections"). So the honest order is PUBLISHER FIRST, then the row -- never a row
for a book that cannot fill it.

WHAT IT PUBLISHES AND WHAT IT DOES NOT CLAIM. `status` is `"paper"`, never
`"online"`: these are paper books and the watchdog's own vocabulary has a word
for that. `extra.mode` carries `backtest|paper|live` so a reader can never
mistake a soak for real money, and `extra.engine` names the package so two
sibling systems are distinguishable on one dashboard.
"""
from __future__ import annotations

import os
from typing import Any

from .logging_setup import get

log = get("fleet_publish")

#: The dashboard row ids this package may write. Declared rather than derived
#: from a config value: a row id is a SHARED key, and a typo'd one silently
#: creates a second row instead of updating the first.
ROW_IDS = {
    "downtrend-ensemble": "downtrend-ensemble-lshadow",
}

_WARNED = [False]


def _store():
    """The fleet's publisher, or None. Never raises, warns exactly once.

    A one-shot warning is right HERE and wrong for a persistent fault: this
    condition is static for the life of the process (the module is either
    importable or it is not), so repeating it every loop would be noise."""
    try:
        import bot_pnl_store                       # type: ignore
        return bot_pnl_store
    except Exception as exc:                       # noqa: BLE001
        if not _WARNED[0]:
            _WARNED[0] = True
            log.info("fleet publishing is OFF (%s). This is normal in a "
                     "standalone checkout.", exc.__class__.__name__)
        return None


def enabled() -> bool:
    """True only when a publish could actually land: the module imports AND a
    database is configured. Both, because an importable module with no
    DATABASE_URL returns False from `publish` forever and looks identical to a
    publisher that is working."""
    if os.environ.get("DOWNTREND_PUBLISH", "").strip().lower() in ("0", "off",
                                                                  "false"):
        return False
    return _store() is not None and bool(os.environ.get("DATABASE_URL"))


def publish(*, row: str, mode: str, equity: float, start_equity: float,
            open_trades: int, closed_trades: int, wins: int, losses: int,
            day_pnl: float | None = None, extra: dict[str, Any] | None = None
            ) -> bool:
    """One dashboard row. Returns whether it landed.

    THE RETURN VALUE IS LOAD-BEARING and callers must not discard it: the
    fleet has already paid for a persistence call whose False was thrown away
    for three days while the organ looked healthy."""
    store = _store()
    if store is None or not enabled():
        return False
    if row not in ROW_IDS.values():
        log.error("refusing to publish to an undeclared row id %r -- a typo'd "
                  "row id creates a SECOND row instead of updating one", row)
        return False
    pnl_abs = equity - start_equity
    pnl_pct = (pnl_abs / start_equity) if start_equity else 0.0
    payload = dict(extra or {})
    payload.update({"mode": mode, "engine": "downtrend_ensemble_bot",
                    "real_money": False})
    status = "halted" if payload.get("soak_ended") else "paper"
    try:
        ok = store.publish(
            bot=row,
            # NEVER "online": this is a paper book, and the watchdog's own
            # vocabulary has a word for that. `online` on a paper row is a
            # claim the book is not entitled to make.
            #
            # A FINISHED SOAK PUBLISHES `halted`, WITH ITS REASON. A research
            # soak is attended and time-boxed, so unlike every other row here
            # it STOPS -- and a row that simply stops updating joins the
            # watchdog's stale list hourly, forever, which is precisely the
            # "a line that is always present is a line nobody reads" failure
            # that file warns about. `halted` is reported as a visible warning
            # rather than a page, and `extra.soak_ended` keeps `halted` from
            # being byte-identical between "the run finished" and "this book
            # lost 5% today".
            status=status,
            equity=round(float(equity), 6),
            pnl_abs=round(float(pnl_abs), 6),
            pnl_pct=round(float(pnl_pct), 8),
            open_trades=int(open_trades), closed_trades=int(closed_trades),
            wins=int(wins), losses=int(losses),
            pnl_daily=(None if day_pnl is None else round(float(day_pnl), 6)),
            extra=payload)
    except Exception as exc:                       # noqa: BLE001
        log.warning("dashboard publish raised (%s); the trading loop is "
                    "unaffected", exc)
        return False
    if not ok:
        log.warning("dashboard publish returned False for %s -- the row is "
                    "NOT current", row)
    return bool(ok)
