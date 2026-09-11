"""Nonce custody: persistence, serialization, reconciliation, UNKNOWN state."""
import threading

import pytest

from lighter_bots.nonce_manager import NonceError, NonceManager


def test_nonces_are_never_reissued(tmp_path):
    nm = NonceManager(str(tmp_path))
    seen = []
    for _ in range(20):
        with nm.reserve(1, 2) as n:
            seen.append(n)
    assert seen == list(range(20))
    assert len(set(seen)) == 20


def test_the_nonce_is_persisted_before_it_is_yielded(tmp_path):
    """Crash-safe direction: a crash may BURN a nonce (cheap) and must never
    re-issue one (not cheap)."""
    nm = NonceManager(str(tmp_path))
    with nm.reserve(1, 2) as n:
        reloaded = NonceManager(str(tmp_path))
        assert reloaded.peek(1, 2) == n + 1, \
            "the store must already show the nonce spent, mid-transaction"


def test_a_crash_mid_transaction_does_not_reissue(tmp_path):
    nm = NonceManager(str(tmp_path))
    with pytest.raises(RuntimeError):
        with nm.reserve(1, 2) as n:
            first = n
            raise RuntimeError("boom")
    with nm.reserve(1, 2) as second:
        assert second == first + 1


def test_a_failed_transaction_is_recorded_UNKNOWN_not_rolled_back(tmp_path):
    nm = NonceManager(str(tmp_path))
    with pytest.raises(RuntimeError):
        with nm.reserve(1, 2):
            raise RuntimeError("timeout -- may have landed")
    ok, why = nm.healthy(1, 2)
    assert not ok and "UNKNOWN" in why
    assert nm.record(1, 2).unknown == [0]


def test_separate_keys_have_separate_sequences(tmp_path):
    nm = NonceManager(str(tmp_path))
    with nm.reserve(1, 2) as a, nm.reserve(1, 3) as b:
        assert a == 0 and b == 0
    with nm.reserve(1, 2) as a2:
        assert a2 == 1


def test_concurrent_reservations_never_collide(tmp_path):
    nm = NonceManager(str(tmp_path))
    got, lock = [], threading.Lock()

    def worker():
        for _ in range(25):
            with nm.reserve(7, 1) as n:
                with lock:
                    got.append(n)

    threads = [threading.Thread(target=worker) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(got) == 150
    assert len(set(got)) == 150, "a reused nonce would show up as a duplicate"
    assert sorted(got) == list(range(150))


def test_reconcile_takes_the_higher_of_local_and_remote(tmp_path):
    nm = NonceManager(str(tmp_path), remote_fetch=lambda a, k: 42)
    assert nm.reconcile(1, 2) == 42
    nm2 = NonceManager(str(tmp_path), remote_fetch=lambda a, k: 5)
    assert nm2.reconcile(1, 2) == 42, \
        "a stale venue read must never walk the local mark backwards"


def test_reconcile_refuses_when_the_venue_cannot_be_read(tmp_path):
    def boom(a, k):
        raise OSError("network")

    nm = NonceManager(str(tmp_path), remote_fetch=boom)
    with pytest.raises(NonceError):
        nm.reconcile(1, 2)


def test_rejection_jumps_to_the_venues_own_answer(tmp_path):
    nm = NonceManager(str(tmp_path))
    with nm.reserve(1, 2):
        pass
    assert nm.note_rejection(1, 2, venue_next=99) == 99
    assert nm.note_rejection(1, 2, venue_next=None) == 100


def test_state_survives_a_restart(tmp_path):
    nm = NonceManager(str(tmp_path))
    for _ in range(3):
        with nm.reserve(4, 5):
            pass
    assert NonceManager(str(tmp_path)).peek(4, 5) == 3


def test_snapshot_carries_no_key_material(tmp_path):
    nm = NonceManager(str(tmp_path))
    with nm.reserve(1, 2):
        pass
    snap = nm.snapshot()
    blob = repr(snap).lower()
    for bad in ("private", "secret", "signature", "0x"):
        assert bad not in blob
    assert snap["1:2"]["next_nonce"] == 1
