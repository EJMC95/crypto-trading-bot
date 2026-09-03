"""[(xu)] `_run` must CLOSE a coroutine it refuses to await.

Every caller builds its coroutine as an argument — `_run(api.foo(...))` — so it
exists before `_run` is entered. The governor check can refuse, and until this
fix it raised with the coroutine never awaited and never closed. Python emits
`RuntimeWarning: coroutine ... was never awaited` and the frame lives until GC.

Observed on 👩 mum's REAL-MONEY row, 3-Sep 00:07Z, on the first entry after her
halt cleared:

    RuntimeWarning: coroutine 'OrderApi.trades' was never awaited
    WLFI entry fill UNMEASURED — skipped:budget(0.9 tok, reserve 6.0)

Not a money bug — the caller's `except` records `api-error:trades:...` and no
order is affected. It is a MEASUREMENT bug: the fill records `slippage NULL`,
and measurement is what this fleet's discipline rests on.

Pinned at the OWNER, not the one call site that happened to surface it: `_run`
is the single place that refuses to run a coroutine, and all 9 of its callers
share the shape.
"""
import asyncio
import gc
import inspect
import os
import sys
import warnings

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from venues.lighter_client import LighterClient, VenueError  # noqa: E402


class _Gov:
    def __init__(self, ok=True, raises=None):
        self.ok, self.raises, self.calls = ok, raises, []

    def acquire(self, weight=None, **kw):
        self.calls.append((weight, kw))
        if self.raises:
            raise self.raises
        return self.ok

    def reward(self):
        pass

    def punish(self):
        pass


class _Stub:
    """Enough of a client for `_run`; no venue, no network, no keys."""
    def __init__(self, gov):
        self.gov = gov
        self._loop = None


async def _never_awaited():
    return "should not run"


def _refuse(gov):
    """Call `_run` with a fresh coroutine; return (raised, coroutine state).

    STATE, NOT A WARNING. The first cut of this test captured
    `RuntimeWarning: ... never awaited` and it was VACUOUS on the
    acquire-raises path: the exception's traceback keeps `_run`'s frame — and
    therefore `coro` — alive, so nothing is collected inside the capture block
    and no warning is ever emitted. A mutation that removed the close SURVIVED.
    `inspect.getcoroutinestate` asks the object directly and cannot be fooled
    by when the collector happens to run.
    """
    coro = _never_awaited()
    raised = None
    try:
        LighterClient._run(_Stub(gov), coro, gov_timeout=0)
    except BaseException as e:  # noqa: BLE001
        raised = e
    state = inspect.getcoroutinestate(coro)
    if state != inspect.CORO_CLOSED:
        coro.close()            # do not leak out of the test either
    return raised, state


def test_a_refused_coroutine_is_closed_not_leaked():
    raised, state = _refuse(_Gov(ok=False))
    assert isinstance(raised, VenueError), raised
    assert "budget exhausted" in str(raised)
    assert state == inspect.CORO_CLOSED, state


def test_an_acquire_that_itself_raises_also_closes_the_coroutine():
    """The governor blowing up leaks the same way, and is the harder path to
    remember — so it is pinned rather than assumed. This is the assertion the
    warning-based first cut could not make: its mutation survived."""
    boom = RuntimeError("governor exploded")
    raised, state = _refuse(_Gov(raises=boom))
    assert raised is boom
    assert state == inspect.CORO_CLOSED, state


def test_no_never_awaited_warning_escapes_a_refusal():
    """Corroboration from the symptom Eamon actually saw in mum's logs."""
    gov = _Gov(ok=False)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        coro = _never_awaited()
        try:
            LighterClient._run(_Stub(gov), coro, gov_timeout=0)
        except VenueError:
            pass
        del coro
        gc.collect()
    leaks = [w for w in caught if issubclass(w.category, RuntimeWarning)
             and "never awaited" in str(w.message)]
    assert leaks == [], [str(w.message) for w in leaks]


def test_cleanup_never_masks_the_governors_own_error():
    """A close() that throws must not replace the error the caller needs."""
    class _Bad:
        def close(self):
            raise ValueError("close blew up")

    gov = _Gov(ok=False)
    with pytest.raises(VenueError, match="budget exhausted"):
        LighterClient._run(_Stub(gov), _Bad(), gov_timeout=0)


def test_the_happy_path_still_awaits_and_returns():
    """The refusal fix must not touch the path that actually runs."""
    loop = asyncio.new_event_loop()
    import threading
    t = threading.Thread(target=loop.run_forever, daemon=True)
    t.start()
    try:
        stub = _Stub(_Gov(ok=True))
        stub._loop = loop
        out = LighterClient._run(stub, _never_awaited(), timeout=5.0)
        assert out == "should not run"   # it DOES run on the happy path
    finally:
        loop.call_soon_threadsafe(loop.stop)
        t.join(timeout=5)


def test_the_governor_is_still_consulted_with_the_callers_weight():
    gov = _Gov(ok=False)
    _refuse(gov)
    assert gov.calls, "the governor must still be asked — this is a rate limiter"
    weight, kw = gov.calls[0]
    assert kw == {"timeout": 0}, kw
