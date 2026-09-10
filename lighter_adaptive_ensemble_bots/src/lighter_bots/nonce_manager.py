"""Per-API-key nonce custody.

A Lighter API key is tied to an ACCOUNT INDEX and carries its OWN nonce
sequence. Two facts make this the most dangerous small module in the package:

  * a REUSED nonce is rejected -- annoying, recoverable;
  * a BLINDLY RETRIED signed order can execute TWICE -- unrecoverable.

So the contract here is deliberately narrow:
  * one lock per (account, key) -- signing is serialized, never concurrent;
  * the nonce is persisted BEFORE it is handed out (crash-safe: a crash can
    burn a nonce, which is cheap, and can never re-issue one, which is not);
  * on restart the local high-water mark is RECONCILED against the venue and
    the HIGHER of the two wins;
  * `reserve()` is a context manager that COMMITS on success and, on failure,
    records the outcome as UNKNOWN rather than rolling back -- because a
    request that timed out may still have landed.
"""
from __future__ import annotations

import json
import os
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator

from .logging_setup import get

log = get("nonce")


class NonceError(RuntimeError):
    pass


@dataclass
class NonceRecord:
    account_index: int
    api_key_index: int
    next_nonce: int = 0
    last_committed: int = -1
    unknown: list[int] = field(default_factory=list)
    updated: float = 0.0

    @property
    def key(self) -> str:
        return f"{self.account_index}:{self.api_key_index}"


class NonceManager:
    """Durable, serialized nonce allocation.

    `remote_fetch` is injected rather than imported so this module can be
    tested exhaustively without an SDK, a network or a private key."""

    def __init__(self, state_dir: str,
                 remote_fetch: Callable[[int, int], int] | None = None):
        self.dir = state_dir
        os.makedirs(self.dir, exist_ok=True)
        self.path = os.path.join(self.dir, "nonces.json")
        self._locks: dict[str, threading.Lock] = {}
        self._guard = threading.Lock()
        self._records: dict[str, NonceRecord] = {}
        self.remote_fetch = remote_fetch
        self._load()

    # ------------------------------------------------------------ storage --
    def _load(self) -> None:
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path) as fh:
                raw = json.load(fh)
        except (OSError, ValueError):
            log.warning("nonce store unreadable; starting from reconciliation")
            return
        for k, v in (raw or {}).items():
            try:
                self._records[k] = NonceRecord(**v)
            except TypeError:
                continue

    def _persist(self) -> None:
        tmp = self.path + ".tmp"
        with open(tmp, "w") as fh:
            json.dump({k: vars(v) for k, v in self._records.items()}, fh,
                      indent=1)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, self.path)          # atomic: never a half-written store

    def _lock_for(self, key: str) -> threading.Lock:
        with self._guard:
            return self._locks.setdefault(key, threading.Lock())

    def record(self, account_index: int, api_key_index: int) -> NonceRecord:
        key = f"{account_index}:{api_key_index}"
        if key not in self._records:
            self._records[key] = NonceRecord(account_index, api_key_index)
        return self._records[key]

    # ------------------------------------------------------ reconciliation --
    def reconcile(self, account_index: int, api_key_index: int) -> int:
        """Restart safety: take max(local high-water, venue). Never lower the
        local mark on a venue read -- a stale or partial venue answer must not
        be able to walk us back onto a nonce we already spent."""
        rec = self.record(account_index, api_key_index)
        remote = None
        if self.remote_fetch is not None:
            try:
                remote = int(self.remote_fetch(account_index, api_key_index))
            except Exception as exc:                       # noqa: BLE001
                raise NonceError(
                    f"could not read the venue nonce for {rec.key}: {exc}. "
                    "Refusing to sign on an unreconciled key.") from exc
        before = rec.next_nonce
        if remote is not None:
            rec.next_nonce = max(rec.next_nonce, remote)
        rec.updated = time.time()
        self._persist()
        log.info("nonce reconciled %s local=%s remote=%s -> %s",
                 rec.key, before, remote, rec.next_nonce)
        return rec.next_nonce

    def peek(self, account_index: int, api_key_index: int) -> int:
        return self.record(account_index, api_key_index).next_nonce

    # ----------------------------------------------------------- allocation --
    @contextmanager
    def reserve(self, account_index: int, api_key_index: int
                ) -> Iterator[int]:
        """Serialized allocation. Persist-then-yield, so a crash burns a nonce
        rather than duplicating one.

        On an exception the nonce is recorded as UNKNOWN (it may have landed)
        and the sequence still advances -- the caller must RECONCILE and
        inspect exchange state, never simply retry with the same value."""
        rec = self.record(account_index, api_key_index)
        lock = self._lock_for(rec.key)
        with lock:
            issued = rec.next_nonce
            rec.next_nonce = issued + 1
            rec.updated = time.time()
            self._persist()
            try:
                yield issued
            except Exception:
                rec.unknown.append(issued)
                rec.updated = time.time()
                self._persist()
                log.error("nonce %s for %s is UNKNOWN: the transaction may "
                          "have landed. Reconcile before any retry.",
                          issued, rec.key)
                raise
            else:
                rec.last_committed = issued
                rec.updated = time.time()
                self._persist()

    def note_rejection(self, account_index: int, api_key_index: int,
                       venue_next: int | None) -> int:
        """A stale/duplicate nonce rejection. Jump to the venue's own answer
        when it gives one; otherwise advance by one and force a reconcile."""
        rec = self.record(account_index, api_key_index)
        if venue_next is not None:
            rec.next_nonce = max(rec.next_nonce, int(venue_next))
        else:
            rec.next_nonce += 1
        rec.updated = time.time()
        self._persist()
        return rec.next_nonce

    def healthy(self, account_index: int, api_key_index: int) -> tuple[bool, str]:
        rec = self.record(account_index, api_key_index)
        if rec.unknown:
            return False, (f"{len(rec.unknown)} nonce(s) in UNKNOWN state "
                           f"({rec.unknown[-3:]}): reconcile exchange state "
                           "before signing again")
        if rec.next_nonce < 0:
            return False, "negative nonce"
        return True, "ok"

    def snapshot(self) -> dict[str, Any]:
        """For logs and reports. Carries no key material by construction."""
        return {k: {"next_nonce": v.next_nonce,
                    "last_committed": v.last_committed,
                    "unknown": len(v.unknown), "updated": v.updated}
                for k, v in self._records.items()}
