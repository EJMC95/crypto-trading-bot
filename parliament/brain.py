#!/usr/bin/env python3
"""
parliament/brain.py — Layer 6: HOWARD 🧠, the ecosystem brain.

The longest-serving PM of the eight watches everything: shared memory,
cross-bot intelligence, and health. Howard TRADES NOTHING — restrict-only
observation and bookkeeping, the fleet's organ doctrine.

SHARED MEMORY   The ecosystem DB is the substrate; Howard curates it:
  * ingests the WIDER fleet's paper_trades ledger (Postgres, guarded) into
    `trades` with source='fleet' — so the Parliament learns ALONGSIDE every
    bot already publishing, and any ecosystem-DB writer joins the loop.
  * prunes old rows daily; persists its own summary to `memory`.

CROSS-BOT INTELLIGENCE
  * VENUE STRESS: reads the Lighter Scout's bot_state `lighter-market`
    (freshness-checked) and pauses NEW Parliament entries when the venue
    |premium| median >= 15bps — the SAME bar and SAME source as the Ticket
    Taker's stress veto. Dark/stale scout restricts nothing (a dark organ
    must not veto) — the books' own gates still apply.
  * per-bot/per-lens rollups from the ecosystem ledger, published for the
    fleet brain (bot_learn) to grade alongside everyone else's rows.

HEALTH   Every Parliament task heartbeats through Howard. A task silent for
3x its expected interval is STALLED: flagged on the published payload, and
(rate-limited, transition-only) pushed to the operator's phone via
NTFY_TOPIC — the watchdog's channel. The supervisor restarts crashed tasks;
Howard is the one who NOTICES quiet ones.

PUBLISHES (freshness contract updated+ttl_sec, consumers go neutral stale):
  bot_state `parliament`        — vitals: books, ML, scanners, health, stress
  bot_state `parliament-tuning` — the tuner bench's active levers
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
import urllib.request
from datetime import datetime, timezone

from . import STATE_KEY, TUNING_STATE_KEY, PM_BOTS, SHADOW_SUFFIX

try:
    import bot_pnl_store as store
except Exception:  # noqa: BLE001
    store = None

try:
    import fleet_bus
except Exception:  # noqa: BLE001
    fleet_bus = None

log = logging.getLogger("parliament.brain")

STRESS_VETO_BPS = float(os.environ.get("PARL_STRESS_VETO_BPS", "15"))
STATE_TTL_SEC = 900
NTFY_MIN_GAP_SEC = 6 * 3600.0

# organ -> expected beat interval (sec); stalled at 3x silence
EXPECTED_BEATS = {
    "data.market": 120, "keating.scanners": 120, "keating.ml": 300,
    **{f"bot.{b}": 60 for b in PM_BOTS},
    **{f"tuner.{b}": 3600 for b in PM_BOTS},
}


class Howard:
    def __init__(self, db, bus=None, ml=None, tuners=None, bots=None):
        self.db = db
        self.bus = bus
        self.ml = ml
        self.tuners = tuners
        self.bots = bots or []
        self.beats: dict[str, tuple[float, str]] = {}
        self.stress_pause = False
        self.stress_med = None
        self._ntfy_sent: dict[str, float] = {}
        self._fleet_ingest_ts = 0.0
        self.started = time.time()

    # -- heartbeat sink (passed to every task as `beat`) ----------------------
    def beat(self, organ: str, note: str = "") -> None:
        self.beats[organ] = (time.time(), note)
        if self.db is not None:
            self.db.beat(organ, note)

    def stalled(self) -> list[str]:
        now = time.time()
        out = []
        for organ, interval in EXPECTED_BEATS.items():
            ts = self.beats.get(organ, (None,))[0]
            grace = self.started + 2 * interval + 600
            if ts is None:
                if now > grace:
                    out.append(organ)
            elif now - ts > 3 * interval + 60:
                out.append(organ)
        return sorted(out)

    # -- cross-bot: venue stress from the Lighter Scout -----------------------
    def refresh_stress(self) -> None:
        self.stress_pause = False
        self.stress_med = None
        if store is None or fleet_bus is None:
            return
        try:
            scout = store.load_state("lighter-market")
            if not scout or not fleet_bus.is_fresh(scout, None):
                return          # dark organ restricts nothing
            med = (scout.get("stress") or {}).get("med")
            if med is None:
                return
            self.stress_med = float(med)
            self.stress_pause = self.stress_med >= STRESS_VETO_BPS
            if self.stress_pause:
                log.info("venue stress veto ON (|prem| med %.1fbps >= %.0f)",
                         self.stress_med, STRESS_VETO_BPS)
        except Exception:  # noqa: BLE001
            self.stress_pause = False

    # -- cross-bot: ingest the fleet's ledger into shared memory --------------
    def ingest_fleet_trades(self) -> int:
        """paper_trades rows from the WIDER fleet -> ecosystem `trades`
        (source='fleet'). No features (their publishers don't record
        entry-time context), so they inform stats, not model training."""
        if store is None or self.db is None:
            return 0
        try:
            rows = store.fetch_paper_trades(limit=1000)
        except Exception:  # noqa: BLE001
            return 0
        n = 0
        own = {b + SHADOW_SUFFIX for b in PM_BOTS} | set(PM_BOTS)
        for r in rows or []:
            try:
                bot = r.get("bot")
                if not bot or bot in own:
                    continue    # our own closes are already first-class rows
                # [2026-07-21 AUDIT FIX — caught by two independent reviewers
                # on day one] fetch_paper_trades returns NORMALIZED keys
                # (close_ts/profit_abs/enter_tag/exit_reason/open_rate/
                # close_rate; there is no trade_id/side/tag/size at all).
                # This ingest read the RAW column names, so every field was
                # None and all of a bot's trades collapsed onto the single id
                # 'fleet-<bot>-None' — "the fleet learns from day one" was a
                # total silent no-op. Keys fixed to the normalized contract;
                # the id is (bot, pair, close_ts) — stable per close, so the
                # upsert dedupes re-fetches instead of collapsing history.
                closed = r.get("close_ts")
                if not closed:
                    continue    # open rows carry no outcome to learn from
                closed_ts = datetime.fromisoformat(
                    str(closed).strip().replace(" UTC", "+00:00")
                    .replace("Z", "+00:00")).timestamp()
                tag = r.get("enter_tag")            # 'long'/'short-<lens>'/None
                side = (tag or "").split("-", 1)[0] or None
                self.db.record_trade(
                    f"fleet-{bot}-{r.get('pair')}-{int(closed_ts)}", bot,
                    "fleet", (r.get("pair") or "").split("/")[0] or None,
                    side, tag, 0.0, closed_ts,
                    r.get("open_rate"), r.get("close_rate"), None,
                    r.get("profit_abs"), r.get("exit_reason"), None)
                n += 1
            except Exception:  # noqa: BLE001
                continue
        self._fleet_ingest_ts = time.time()
        return n

    # -- rollups --------------------------------------------------------------
    def book_summary(self) -> dict:
        out = {}
        for bot in self.bots:
            if bot.broker is None:
                continue
            eq = bot.broker.equity()
            out[bot.base] = {
                "label": PM_BOTS[bot.base][0], "equity": round(eq, 2),
                "pnl": round(eq - bot.broker.start, 2),
                "open": len(bot.broker.pos),
                "closed": bot.wins + bot.losses,
                "wins": bot.wins, "losses": bot.losses,
                "halted": bot.halted_today, "last_skip": bot.last_skip,
            }
        return out

    def lens_rollup(self, days: float = 7.0) -> dict:
        """Per-(bot, lens) expectancy from the ecosystem ledger — the same
        cut bot_learn grades, published so the two brains can be compared."""
        if self.db is None:
            return {}
        out: dict[str, dict] = {}
        for t in self.db.closed_trades(days=days):
            if t.get("source") != "parliament" or t.get("pnl_abs") is None:
                continue
            key = f"{t['bot']}:{t.get('tag') or '?'}"
            slot = out.setdefault(key, {"n": 0, "pnl": 0.0, "wins": 0})
            slot["n"] += 1
            slot["pnl"] = round(slot["pnl"] + t["pnl_abs"], 4)
            slot["wins"] += 1 if t["pnl_abs"] > 0 else 0
        return out

    # -- publish --------------------------------------------------------------
    def publish(self, data=None, scanners=None) -> dict:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        stalled = self.stalled()
        payload = {
            "updated": now, "ttl_sec": STATE_TTL_SEC,
            "roster": {"brain": "howard", "intelligence": "keating",
                       "books": list(PM_BOTS)},
            "books": self.book_summary(),
            "lens_7d": self.lens_rollup(),
            "ml": self.ml.snapshot() if self.ml else {"enabled": False},
            "tuning": self.tuners.snapshot() if self.tuners else {},
            "stress": {"med_bps": self.stress_med,
                       "pause": self.stress_pause,
                       "bar_bps": STRESS_VETO_BPS},
            "data": {"books": len(getattr(data, "market", {}) or {}),
                     "watchlist": list(getattr(data, "watchlist", []) or []),
                     "cycles": getattr(data, "cycles", 0),
                     "errors": getattr(data, "errors", 0)} if data else {},
            "scanners": {"emitted": getattr(scanners, "emitted", 0),
                         # the full 10-scanner bench, quiet members included —
                         # per-scanner counts/last-fire so no scanner can go
                         # dark invisibly behind the lump-sum number
                         "bench": {
                             name: {"n": b.get("emitted", 0),
                                    "runs": b.get("runs", 0),
                                    "last_sym": b.get("last_sym"),
                                    "last_age_sec": (
                                        int(time.time() - b["last_ts"])
                                        if b.get("last_ts") else None)}
                             for name, b in sorted(
                                 (getattr(scanners, "by_scanner", None)
                                  or {}).items())}},
            "health": {"stalled": stalled,
                       "beats": {k: int(time.time() - v[0])
                                 for k, v in sorted(self.beats.items())}},
        }
        if store is not None:
            try:
                store.save_state(STATE_KEY, payload)
                store.save_history(STATE_KEY, payload)
            except Exception:  # noqa: BLE001
                pass
            try:
                store.save_state(TUNING_STATE_KEY, {
                    "updated": now, "ttl_sec": STATE_TTL_SEC,
                    **(self.tuners.snapshot() if self.tuners else {})})
            except Exception:  # noqa: BLE001
                pass
        if self.db is not None:
            self.db.remember("howard.last", payload)
        for organ in stalled:
            self._notify_stall(organ)
        return payload

    def _notify_stall(self, organ: str) -> None:
        topic = os.environ.get("NTFY_TOPIC", "").strip()
        if not topic:
            return
        now = time.time()
        if now - self._ntfy_sent.get(organ, 0.0) < NTFY_MIN_GAP_SEC:
            return
        self._ntfy_sent[organ] = now
        try:
            req = urllib.request.Request(
                f"https://ntfy.sh/{topic}",
                data=f"🏛️ Parliament: organ '{organ}' stalled".encode(),
                headers={"Title": "Parliament health", "Priority": "high",
                         "Tags": "warning"})
            urllib.request.urlopen(req, timeout=10)
        except Exception:  # noqa: BLE001
            pass

    # -- loop -----------------------------------------------------------------
    async def run_forever(self, data=None, scanners=None,
                          interval: float = 300.0):
        last_prune = 0.0
        while True:
            try:
                self.refresh_stress()
                if time.time() - self._fleet_ingest_ts > 3600.0:
                    n = self.ingest_fleet_trades()
                    if n:
                        log.info("ingested %d fleet trades into shared memory", n)
                if self.db is not None and time.time() - last_prune > 86400.0:
                    self.db.prune()
                    last_prune = time.time()
                self.publish(data=data, scanners=scanners)
                self.beat("howard", "ok")
            except Exception as e:  # noqa: BLE001
                log.exception("howard cycle failed (%s)", e)
            await asyncio.sleep(interval)
