#!/usr/bin/env python3
"""
parliament/bus.py — the Parliament's pub/sub bus.

One process, many organs: scanners publish signals, bots subscribe, the ML
engine and Howard listen to everything. The PRIMARY transport is in-process
asyncio queues (every layer is a task in parliament_main.py, so this is a
complete, dependency-free bus). When REDIS_URL is set AND the `redis` wheel
is importable, every publish is MIRRORED to Redis pub/sub on the same topic
(prefix `parliament.`) so out-of-process consumers can listen too — mirror
only, never a dependency: Redis down/absent changes nothing in-process.

Topics (dot-namespaced, payloads are plain dicts):
  signals.<scanner>   one scanner emission (sym, direction, strength, ...)
  market.snapshot     the data layer's per-cycle market map
  trade.opened / trade.closed
  tuning.applied      a tuner lever enact/expire event
  health.beat         organ heartbeats (Howard consumes)

Fail-safe contract: publish() never raises; a slow subscriber drops its own
oldest messages (bounded queues), never anyone else's.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time

log = logging.getLogger("parliament.bus")

_QUEUE_MAX = 512


class EcosystemBus:
    def __init__(self):
        self._subs: dict[str, list[asyncio.Queue]] = {}
        self._redis = None
        self._redis_dead = False          # permanent: no URL / wheel absent
        self._redis_retry_at = 0.0        # transient-error backoff stamp
        self.published = 0          # lifetime counters, surfaced by Howard
        self.dropped = 0

    # -- in-process pub/sub ---------------------------------------------------
    def subscribe(self, *topics: str) -> asyncio.Queue:
        """Register a bounded queue for one or more topics. Returns the queue;
        messages arrive as (topic, payload) tuples."""
        q: asyncio.Queue = asyncio.Queue(maxsize=_QUEUE_MAX)
        for t in topics:
            self._subs.setdefault(t, []).append(q)
        return q

    def publish(self, topic: str, payload: dict) -> None:
        """Fan out to every subscriber of `topic` and of its parents
        (`signals.breakout` also reaches a `signals` subscriber). Never raises."""
        self.published += 1
        msg = (topic, payload)
        seen: set[int] = set()
        parts = topic.split(".")
        keys = [".".join(parts[: i + 1]) for i in range(len(parts))]
        for key in keys:
            for q in self._subs.get(key, ()):
                if id(q) in seen:
                    continue
                seen.add(id(q))
                try:
                    q.put_nowait(msg)
                except asyncio.QueueFull:
                    # drop the OLDEST so a stalled consumer sees fresh data
                    # when it wakes, and never blocks a publisher.
                    try:
                        q.get_nowait()
                        q.put_nowait(msg)
                    except Exception:
                        pass
                    self.dropped += 1
        self._mirror(topic, payload)

    # -- optional Redis mirror ------------------------------------------------
    _REDIS_RETRY_SEC = 300.0

    def _mirror(self, topic: str, payload: dict) -> None:
        if self._redis_dead or time.time() < self._redis_retry_at:
            return
        url = os.environ.get("REDIS_URL", "").strip()
        if not url:
            self._redis_dead = True
            return
        try:
            if self._redis is None:
                try:
                    import redis  # optional wheel — absent is a supported state
                except Exception:  # noqa: BLE001 — permanently absent
                    self._redis_dead = True
                    return
                self._redis = redis.Redis.from_url(
                    url, socket_timeout=2, socket_connect_timeout=2)
            self._redis.publish("parliament." + topic,
                                json.dumps(payload, default=str))
        except Exception as e:  # noqa: BLE001 — mirror only, go quiet
            # [2026-07-21 AUDIT FIX] one transient error used to disable the
            # mirror for the PROCESS LIFETIME (potentially weeks). Back off
            # instead: dead until the retry stamp, then one reconnect
            # attempt; repeated failure just re-arms the backoff. In-process
            # bus unaffected either way.
            log.info("redis mirror off (%s) — retrying in %.0fs; in-process "
                     "bus unaffected", e, self._REDIS_RETRY_SEC)
            self._redis = None
            self._redis_retry_at = time.time() + self._REDIS_RETRY_SEC


async def drain(q: asyncio.Queue, max_items: int = 200) -> list:
    """Non-blocking drain of everything queued (up to max_items)."""
    out = []
    for _ in range(max_items):
        try:
            out.append(q.get_nowait())
        except asyncio.QueueEmpty:
            break
    return out


def selfcheck() -> None:
    """Offline invariants (run by parliament_main --selftest)."""

    async def _run():
        bus = EcosystemBus()
        q_all = bus.subscribe("signals")
        q_one = bus.subscribe("signals.breakout")
        bus.publish("signals.breakout", {"sym": "BTC", "strength": 1.0})
        bus.publish("signals.funding", {"sym": "ETH", "strength": 0.5})
        got_all = await drain(q_all)
        got_one = await drain(q_one)
        assert len(got_all) == 2, got_all          # parent topic sees both
        assert len(got_one) == 1, got_one          # exact topic sees its own
        assert got_one[0][0] == "signals.breakout"
        # bounded queue: overflow drops oldest, publisher never blocks
        q_small = bus.subscribe("flood")
        for i in range(_QUEUE_MAX + 10):
            bus.publish("flood", {"i": i})
        flood = await drain(q_small, max_items=_QUEUE_MAX + 20)
        assert len(flood) == _QUEUE_MAX
        assert flood[-1][1]["i"] == _QUEUE_MAX + 9, "newest must survive"
        assert bus.dropped >= 10

    asyncio.run(_run())
    print("parliament.bus selfcheck OK")
