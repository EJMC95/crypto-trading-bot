"""[(lj)] The organ-death chain: writer -> caller -> consumer, end to end.

`(hw)` built this because `run_all.sh` runs every organ as
`python3 <organ>.py || true`, so a crash sends its exit code to `|| true` and
its traceback to a container log nobody tails. Measured that day: **20 of 22
organs had no way to report their own death**, and the learning brain had been
raising `KeyError('paper')` on every run for weeks — publishing its read-only
keys on time, looking perfectly healthy, while its memory could never advance.

THE MECHANISM WAS DEAD IN THREE PLACES AT ONCE, which is exactly why no single
one of them was noticed:

  1. **The writer never wrote.** `record_organ_error` calls
     `datetime.now(timezone.utc)`, and `datetime` is not a module-level name in
     `bot_pnl_store` — every other user imports it locally. So it raised
     NameError on EVERY call, the blanket `except Exception: return False`
     swallowed it, and `save_state` was never reached. Proven by stubbing both
     DB calls to succeed: the function still returned False and still never
     called `save_state`.
  2. **The caller lied about it.** `organ_main` discarded that False and
     printed *"ORGAN FAULT recorded on its own bot_state key so the immune
     organ can see it"* unconditionally — I4's discarded result and I8's
     unactionable instruction in one line.
  3. **Nothing read the field.** `clear_organ_error` is called by no organ, and
     `healthy` appeared in no consumer anywhere in the tree.

A writer that never wrote, a clearer nobody calls, and no reader. Fixing only
the import would have left a signal that still reached nobody — *"a finding no
gate consumes is a note"*.
"""
import sys
import types

import pytest

pytestmark = pytest.mark.autonomy

import bot_pnl_store as S          # noqa: E402
import fleet_immune as FI          # noqa: E402


@pytest.fixture
def store(monkeypatch):
    """The real module with only its DB edges stubbed, so the code under test
    is the shipped code and not a re-description of it."""
    written = {}
    monkeypatch.setattr(S, "load_state", lambda k: dict(written.get(k) or {}))

    def save_state(k, p):
        written[k] = dict(p)
        return True

    monkeypatch.setattr(S, "save_state", save_state)
    return written


# ---------------------------------------------------------------------------
# 1 · the WRITER actually writes
# ---------------------------------------------------------------------------

def test_record_organ_error_reaches_save_state(store):
    """The bug: NameError before the write, swallowed, returning False.

    Both DB calls succeed here, so a False return or an unwritten key can only
    mean the function aborted internally.
    """
    ok = S.record_organ_error("brain-vitals", KeyError("paper"),
                              "bot_learn.py:1200")
    assert ok is True, "record_organ_error returned False with a working store"
    assert "brain-vitals" in store, "it never reached save_state"


def test_the_stamp_carries_what_the_operator_needs(store):
    S.record_organ_error("brain-vitals", KeyError("paper"), "bot_learn.py:1200")
    p = store["brain-vitals"]
    assert p["healthy"] is False
    assert "KeyError" in p["error"] and "paper" in p["error"]
    assert p["error_where"] == "bot_learn.py:1200"
    assert p["error_at"], "no timestamp — the operator cannot age the death"


def test_it_preserves_the_organs_existing_payload(store):
    """save_state replaces a payload WHOLESALE, so the error stamp must merge
    into the organ's own keys rather than blanking them."""
    store["brain-vitals"] = {"run": 338, "engine": "v3"}
    S.record_organ_error("brain-vitals", ValueError("boom"))
    p = store["brain-vitals"]
    assert p["run"] == 338 and p["engine"] == "v3"
    assert p["healthy"] is False


def test_it_still_never_raises(monkeypatch):
    """The never-raise contract is load-bearing: this runs inside the handler
    for another exception."""
    monkeypatch.setattr(S, "load_state",
                        lambda k: (_ for _ in ()).throw(RuntimeError("db")))
    assert S.record_organ_error("x", ValueError("y")) is False


# ---------------------------------------------------------------------------
# 2 · the CALLER tells the truth
# ---------------------------------------------------------------------------

def test_organ_main_records_a_fault_and_says_so(store, capsys):
    def boom():
        raise KeyError("paper")

    rc = S.organ_main("brain-vitals", boom)
    assert rc == 1
    assert store["brain-vitals"]["healthy"] is False
    err = capsys.readouterr().err
    assert "ORGAN FAULT recorded" in err


def test_organ_main_does_not_claim_a_recording_that_failed(monkeypatch, capsys):
    """The false sentence. It printed 'recorded ... so the immune organ can see
    it' on every call, including the years-long stretch where nothing was ever
    recorded."""
    monkeypatch.setattr(S, "record_organ_error", lambda *a, **k: False)

    def boom():
        raise KeyError("paper")

    S.organ_main("brain-vitals", boom)
    err = capsys.readouterr().err
    assert "COULD NOT BE RECORDED" in err, err
    assert "ORGAN FAULT recorded on its own bot_state key" not in err


def test_a_clean_organ_records_nothing(store, capsys):
    """Control group: organ_main must not stamp a fault on a successful run."""
    assert S.organ_main("brain-vitals", lambda: None) == 0
    assert "brain-vitals" not in store


# ---------------------------------------------------------------------------
# 3 · the CONSUMER surfaces it
# ---------------------------------------------------------------------------

def test_the_immune_organ_reports_a_recorded_death():
    out = FI.organ_faults({"brain-vitals": {
        "healthy": False, "error": "KeyError: 'paper'",
        "error_where": "bot_learn.py:1200",
        "error_at": "2026-08-07T02:00:00+00:00"}})
    assert len(out) == 1
    assert out[0]["organ"] == "brain-vitals"
    d = out[0]["detail"]
    assert "ORGAN DIED" in d and "KeyError" in d
    assert "bot_learn.py:1200" in d, "I8: name the object the operator can act on"


def test_a_healthy_or_unstamped_organ_is_silent():
    """A detector that flags everything trains the operator to ignore it.

    `healthy` absent means the organ has never stamped either way — that is not
    a fault, and treating it as one would fire on every organ in the fleet.
    """
    assert FI.organ_faults({
        "fleet-risk": {"healthy": True, "run": 5},
        "regime-oracle": {"run": 9},
        "lighter-market": {},
        "empty": None,
    }) == []


def test_it_is_not_gated_on_freshness():
    """Deliberately inverted from `organ_invariants`, which asks 'is this
    CONTENT true now?' and so must skip stale payloads. This asks 'did this
    organ die?' — and a dead organ is precisely the one that stops refreshing
    its key, so a freshness gate would mute the loudest case."""
    stale = {"healthy": False, "error": "RuntimeError: x",
             "updated": "2026-01-01T00:00:00+00:00", "ttl_sec": 60}
    assert FI.organ_faults({"some-organ": stale}), (
        "a long-dead organ was skipped — freshness must not gate a death report")


def test_the_consumer_is_wired_into_the_sick_list():
    """Without this the scanner is dead code — the registered-but-inert shape
    this organ has been bitten by three times ((hh), the churn counter,
    brain_amnesia)."""
    import ast
    import inspect
    src = inspect.getsource(FI.run_once)
    tree = ast.parse(src.lstrip())
    called = {n.func.id for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "organ_faults" in called, (
        "organ_faults is defined but never called from run_once")


def test_the_whole_chain_end_to_end(store):
    """Writer -> caller -> consumer, with only the DB edges stubbed.

    This is the test that would have failed on the shipped code at every one of
    the three broken links, and the reason it is here rather than three unit
    tests: each link looked fine in isolation.
    """
    def boom():
        raise KeyError("paper")

    S.organ_main("brain-vitals", boom)
    faults = FI.organ_faults(store)
    assert [f["organ"] for f in faults] == ["brain-vitals"]
    assert "paper" in faults[0]["detail"]
