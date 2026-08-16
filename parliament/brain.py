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

from . import (STATE_KEY, TUNING_STATE_KEY, PM_BOTS, SHADOW_SUFFIX,
               live_pm_bots as _live_pm)

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
#
# [2026-08-16 (nz)] BUILT FROM THE LIVE ROSTER, NOT THE RAW DECLARATION.
# `(nf)` retired four PM books via `PM_RETIRED`/`live_pm_bots()` and pinned
# `build_bots` to the derivation — but THIS table kept expecting a heartbeat
# from all six, so the four retired books read STALLED (3x silence) forever
# and Howard paged the operator about books that are retired BY DESIGN. The
# (mo) rule is one declaration, one derivation, and it has to reach every
# consumer that makes a LIVE claim — a watchdog that cries wolf about a
# deliberate decision is how a real stall later gets ignored ((gl)).
# Computed at import like before; a resurrection via the override env is a
# process restart, which re-imports this module.
def _expected_beats():
    from . import live_pm_bots
    live = live_pm_bots()
    return {
        "data.market": 120, "keating.scanners": 120, "keating.ml": 300,
        **{f"bot.{b}": 60 for b in live},
        **{f"tuner.{b}": 3600 for b in live},
    }


EXPECTED_BEATS = _expected_beats()


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
        self._restarts = None
        self.note_restart()   # [(nz)] persisted, survives the container

    # -- heartbeat sink (passed to every task as `beat`) ----------------------
    def beat(self, organ: str, note: str = "") -> None:
        self.beats[organ] = (time.time(), note)
        if self.db is not None:
            self.db.beat(organ, note)

    # -- [(nz)] durable restart counter --------------------------------------
    _RESTART_KEY = "supervisor.restarts"

    def note_restart(self) -> int:
        """Bump the persisted restart count ONCE per process and return it.

        Called at construction. The ecosystem DB lives on the Railway persist
        volume, so this survives the container the way `cycles` does not.
        Never raises: a dark DB costs the count, never the boot."""
        try:
            prev = (self.db.recall(self._RESTART_KEY) or {}) if self.db else {}
            n = int(prev.get("n") or 0) + 1
            if self.db is not None:
                self.db.remember(self._RESTART_KEY,
                                 {"n": n, "last": datetime.now(timezone.utc)
                                  .isoformat(timespec="seconds")})
            self._restarts = n
            return n
        except Exception:  # noqa: BLE001
            self._restarts = getattr(self, "_restarts", None)
            return self._restarts or 0

    def build_stamp(self):
        """[(oi)] The image this process is running, so a restart can be told
        from a DEPLOY. Content hash via the fleet's one owner
        (`bot_pnl_store.build_compute`, cached there); None when the store is
        dark — UNKNOWN, never a fake constant that would make every deploy
        look like a crash."""
        try:
            if store is None:
                return None
            if getattr(self, "_build", None) is None:
                self._build = store.build_compute("parliament_main.py")[0]
            return self._build
        except Exception:  # noqa: BLE001
            return None

    def restart_count(self):
        """What the payload publishes. None when the DB could not answer —
        UNKNOWN must not read as zero (the absence-is-not-evidence rule)."""
        return getattr(self, "_restarts", None)

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

    def fleet_lens_rollup(self, days: float = 7.0) -> dict:
        """[2026-07-28 AUDIT FIX] Per-tag expectancy of the WIDER fleet's
        ingested closes (source='fleet') — the loop-closer the hourly ingest
        never had. ingest_fleet_trades wrote up to 1000 rows/hour and
        NOTHING consumed them (ML filters on features the fleet rows never
        carry; tuners + lens_rollup filter source='parliament'): a
        write-only table wearing a "Howard learns from every bot" claim.
        This is the cheap, honest close: the fleet's per-tag expectancy on
        the SAME cut and window as lens_7d, published side by side so the
        two-brains comparison is a read, not a promise."""
        if self.db is None:
            return {}
        out: dict[str, dict] = {}
        for t in self.db.closed_trades(days=days):
            if t.get("source") != "fleet" or t.get("pnl_abs") is None:
                continue
            key = str(t.get("tag") or "?")
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
            # [2026-08-16 (nz)] THE DEATH COUNTER THAT SURVIVES THE DEATH,
            # published at TOP level on purpose — `data.cycles` RESETS every
            # restart and `data.errors` read 0 through TEN supervisor restarts
            # in 48h (measured off the bus series; fleet_immune caught it from
            # OUTSIDE and phone-pushed, while this payload said nothing) — the
            # I13 shape: a process that STOPS runs no handler, so its own
            # counters are the ones guaranteed not to notice. Persisted in the
            # ecosystem DB (Railway volume), monotone, and OUTSIDE the `data`
            # block because a dark data layer is exactly when you need it.
            # None = the DB could not answer; UNKNOWN must not read as zero.
            "restarts": self.restart_count(),
            # [(oi)] the running image, beside the count: an increment WITH a
            # new build is a deploy, an increment on the SAME build is a crash
            "build": self.build_stamp(),
            # [(nz)] the published roster is the LIVING one — this key is a
            # claim about what the Parliament is running now, and it read six
            # books while four were retired. (The ingest filter at
            # `ingest_fleet` keeps using raw PM_BOTS on purpose: a retired
            # book's HISTORICAL closes are still Howard's own rows.)
            "roster": {"brain": "howard", "intelligence": "keating",
                       "books": sorted(_live_pm())},
            "books": self.book_summary(),
            "lens_7d": self.lens_rollup(),
            "fleet_lens_7d": self.fleet_lens_rollup(),
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
