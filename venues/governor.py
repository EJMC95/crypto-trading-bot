#!/usr/bin/env python3
"""
venues/governor.py — weighted request budget for the Lighter standard tier.

Verified constraint (docs/lighter.md): 60 WEIGHTED requests/min per L1
address, shared REST+tx. Order txs weigh 6 (sendTxBatch the same — batch!).
Websocket market data is effectively free (200 conns/IP, 500 subs/conn), so
the client is ws-first and REST goes through this governor.

The budget is per L1 ADDRESS, i.e. fleet-wide across every Railway service
trading the same account family. True distributed limiting is overkill for a
two-bot pilot; instead each PROCESS takes an env-assigned SHARE of the minute
budget and backs off hard on 429/405:

    LIGHTER_BUDGET_SHARE   fraction of the 60/min this process may use
                           (default 0.35 — two pilot services + headroom)
    LIGHTER_BUDGET_PER_MIN override the absolute weighted budget (default 60)

Backoff: any 429/405 empties the local bucket and doubles a cooldown (capped
at 5 min) so one bot's cascade cannot starve the account budget for the rest.
Thread-safe; one instance per process (venues.market_data shares it).
"""
from __future__ import annotations

import os
import threading
import time

WEIGHT_INFO = 1      # plain REST info call
WEIGHT_ORDER_TX = 6  # sendTx / sendTxBatch (empirical, docs/lighter.md)


class TxBudgetGovernor:
    def __init__(self, budget_per_min: float | None = None, share: float | None = None):
        budget = float(budget_per_min if budget_per_min is not None
                       else os.environ.get("LIGHTER_BUDGET_PER_MIN", 60))
        share = float(share if share is not None
                      else os.environ.get("LIGHTER_BUDGET_SHARE", 0.35))
        self.capacity = max(1.0, budget * share)
        self.tokens = self.capacity
        self.rate = self.capacity / 60.0          # refill per second
        self.updated = time.monotonic()
        self.cooldown_until = 0.0
        self.cooldown_len = 5.0                   # doubles per 429/405, cap 300s
        self._lock = threading.Lock()

    def _refill(self):
        now = time.monotonic()
        self.tokens = min(self.capacity, self.tokens + (now - self.updated) * self.rate)
        self.updated = now

    def acquire(self, weight: float = WEIGHT_INFO, timeout: float = 120.0) -> bool:
        """Block until `weight` tokens are available (or timeout). Returns False
        on timeout so callers can skip the loop instead of hammering."""
        deadline = time.monotonic() + timeout
        while True:
            with self._lock:
                self._refill()
                now = time.monotonic()
                if now >= self.cooldown_until and self.tokens >= weight:
                    self.tokens -= weight
                    return True
                wait = max(self.cooldown_until - now,
                           (weight - self.tokens) / self.rate if self.tokens < weight else 0.05)
            if time.monotonic() + wait > deadline:
                return False
            time.sleep(min(wait, 2.0))

    def punish(self):
        """Call on HTTP 429/405: drain the bucket and back off exponentially."""
        with self._lock:
            self.tokens = 0.0
            self.updated = time.monotonic()
            self.cooldown_until = self.updated + self.cooldown_len
            self.cooldown_len = min(self.cooldown_len * 2, 300.0)

    def reward(self):
        """Call on a successful request: relax the backoff ladder."""
        with self._lock:
            self.cooldown_len = max(5.0, self.cooldown_len * 0.5)
