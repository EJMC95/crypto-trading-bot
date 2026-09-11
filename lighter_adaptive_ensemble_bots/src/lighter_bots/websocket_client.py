"""WebSocket lifecycle: reconnect, resubscribe, sequence checks, staleness.

The design assumption is that the socket WILL drop and WILL silently go stale,
because both are routine. So:

  * a drop triggers exponential backoff with jitter (a fixed backoff makes
    every client in a fleet reconnect in lockstep and re-drop together);
  * every reconnect ends with a REST RECONCILIATION callback -- the socket is
    a low-latency convenience, the REST state is the truth;
  * `stale_for()` is checked by the caller each loop, because a socket that
    is OPEN and silent looks identical to a quiet market and is the failure
    the per-message handlers cannot see;
  * out-of-order and DUPLICATE events are dropped by sequence, so a replay
    after reconnect cannot double-count a fill.

The transport is injected. That keeps this module unit-testable without a
network and lets `lighter.WsClient` be swapped in without changing the logic.
"""
from __future__ import annotations

import json
import random
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from .logging_setup import get

log = get("ws")


@dataclass
class Subscription:
    channel: str
    params: dict[str, Any] = field(default_factory=dict)

    @property
    def key(self) -> str:
        return f"{self.channel}:{json.dumps(self.params, sort_keys=True)}"


class WebSocketManager:
    def __init__(self, url: str, *,
                 connect: Callable[[str], Any] | None = None,
                 on_reconcile: Callable[[], None] | None = None,
                 max_backoff: float = 60.0, stale_after: float = 45.0,
                 ping_interval: float = 20.0):
        self.url = url
        self._connect = connect
        self.on_reconcile = on_reconcile
        self.max_backoff = max_backoff
        self.stale_after = stale_after
        self.ping_interval = ping_interval

        self.subs: dict[str, Subscription] = {}
        self.conn: Any | None = None
        self.connected = False
        self.last_message_at: float = 0.0
        self.last_ping_at: float = 0.0
        self.reconnects = 0
        self.attempt = 0
        self.dropped_duplicates = 0
        self.dropped_out_of_order = 0
        self._seq: dict[str, int] = {}
        self._seen: dict[str, set] = {}
        self._lock = threading.Lock()
        self.handlers: dict[str, Callable[[dict], None]] = {}

    # ------------------------------------------------------------ backoff --
    def backoff_delay(self, attempt: int | None = None) -> float:
        a = self.attempt if attempt is None else attempt
        base = min(self.max_backoff, (2.0 ** max(0, a)) * 0.5)
        return base * (0.5 + random.random() * 0.5)      # jitter: 50-100%

    # -------------------------------------------------------- connection ---
    def subscribe(self, channel: str, **params: Any) -> Subscription:
        s = Subscription(channel, params)
        with self._lock:
            self.subs[s.key] = s
        if self.connected and self.conn is not None:
            self._send_subscribe(s)
        return s

    def _send_subscribe(self, s: Subscription) -> None:
        try:
            send = getattr(self.conn, "send", None)
            if callable(send):
                send(json.dumps({"type": "subscribe", "channel": s.channel,
                                 **s.params}))
        except Exception as exc:                        # noqa: BLE001
            log.warning("subscribe failed for %s: %s", s.key, exc)

    def connect(self, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        if self._connect is None:
            return False
        try:
            self.conn = self._connect(self.url)
        except Exception as exc:                        # noqa: BLE001
            self.attempt += 1
            self.connected = False
            log.warning("ws connect failed (attempt %d): %s", self.attempt, exc)
            return False
        self.connected = True
        self.attempt = 0
        self.last_message_at = now
        self.last_ping_at = now
        for s in list(self.subs.values()):
            self._send_subscribe(s)
        if self.on_reconcile is not None:
            # REST is the truth after every (re)connect -- always, not only
            # after an error, because a clean reconnect can still have missed
            # events while the socket was down.
            try:
                self.on_reconcile()
            except Exception as exc:                     # noqa: BLE001
                log.error("post-connect reconciliation failed: %s", exc)
        return True

    def disconnect(self, reason: str = "requested") -> None:
        self.connected = False
        self.reconnects += 1
        log.info("ws disconnected: %s (reconnects=%d)", reason, self.reconnects)
        try:
            close = getattr(self.conn, "close", None)
            if callable(close):
                close()
        except Exception:                               # noqa: BLE001
            pass
        self.conn = None

    # ----------------------------------------------------------- messages --
    def on(self, channel: str, fn: Callable[[dict], None]) -> None:
        self.handlers[channel] = fn

    def handle(self, msg: dict[str, Any], now: float | None = None) -> bool:
        """-> True when the message was accepted. Duplicates and out-of-order
        events are dropped and COUNTED, never processed."""
        now = time.time() if now is None else now
        self.last_message_at = now
        ch = str(msg.get("channel") or msg.get("type") or "")
        seq = msg.get("seq", msg.get("sequence"))
        eid = msg.get("id", msg.get("event_id"))

        if eid is not None:
            seen = self._seen.setdefault(ch, set())
            if eid in seen:
                self.dropped_duplicates += 1
                return False
            seen.add(eid)
            if len(seen) > 5000:
                self._seen[ch] = set(list(seen)[-2500:])
        if seq is not None:
            try:
                seq_i = int(seq)
            except (TypeError, ValueError):
                seq_i = None
            if seq_i is not None:
                last = self._seq.get(ch)
                if last is not None and seq_i <= last:
                    self.dropped_out_of_order += 1
                    return False
                if last is not None and seq_i > last + 1:
                    log.warning("ws gap on %s: %s -> %s; reconciling",
                                ch, last, seq_i)
                    if self.on_reconcile is not None:
                        self.on_reconcile()
                self._seq[ch] = seq_i
        fn = self.handlers.get(ch)
        if fn is not None:
            fn(msg)
        return True

    # ------------------------------------------------------------- health --
    def stale_for(self, now: float | None = None) -> float:
        now = time.time() if now is None else now
        if not self.last_message_at:
            return float("inf") if self.connected else 0.0
        return max(0.0, now - self.last_message_at)

    def is_stale(self, now: float | None = None) -> bool:
        return self.connected and self.stale_for(now) > self.stale_after

    def maybe_ping(self, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        if not self.connected or now - self.last_ping_at < self.ping_interval:
            return False
        self.last_ping_at = now
        try:
            ping = getattr(self.conn, "ping", None)
            if callable(ping):
                ping()
            return True
        except Exception as exc:                        # noqa: BLE001
            log.warning("ping failed: %s", exc)
            self.disconnect("ping failed")
            return False

    def tick(self, now: float | None = None) -> dict[str, Any]:
        """One supervision step. Returns the health the caller reports."""
        now = time.time() if now is None else now
        if self.connected and self.is_stale(now):
            self.disconnect(f"stale for {self.stale_for(now):.0f}s")
        if not self.connected:
            delay = self.backoff_delay()
            self.connect(now)
            if not self.connected:
                return self.health(now) | {"retry_in_s": round(delay, 2)}
        self.maybe_ping(now)
        return self.health(now)

    def health(self, now: float | None = None) -> dict[str, Any]:
        return {"connected": self.connected,
                "stale_s": round(self.stale_for(now), 2),
                "subscriptions": len(self.subs),
                "reconnects": self.reconnects,
                "dropped_duplicates": self.dropped_duplicates,
                "dropped_out_of_order": self.dropped_out_of_order}
