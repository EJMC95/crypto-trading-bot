"""[(lj)] I2's declared enforcement must be able to FIRE.

CLAUDE.md's invariant table says:

    ### I2 · A CONSTANT LAG IS INVISIBLE — MEASURE THE THING THAT DIVERGES
      ENFORCED BY: `fleet_immune.py::brain_amnesia`

and the same file's header warns, in terms:

    "What a green run does NOT mean: it verifies that a declared enforcement
     EXISTS, not that it is CORRECT. A named test could be vacuous."

That prediction had come true. `brain_amnesia` computes
`vitals.updated - brain.updated` and returns `[]` the moment either stamp is
unreadable — and **the brain's memory payload never carried one**:

  * `bot_learn._save_state` writes the raw `state` dict; nothing in that module
    ever set `state["updated"]`.
  * `bot_pnl_store.save_state` records the time in the bot_state `updated_at`
    COLUMN, not inside the JSON.
  * `fleet_immune` reads via `store.fetch_states`, whose SQL is
    `SELECT bot, state` — the column is never merged in.

So `b.get("updated") or b.get("updated_at")` was `None` on every real cycle,
`bt is None` short-circuited, and the guard returned `[]` forever. **No test
covered it**, and `audit_doctrine_enforcement` stayed green throughout because
the reference resolves — the function exists.

The detector had been written against what a human sees in `psql` (where
`updated_at` is a visible column) rather than against what its publisher emits.
That is the `(hj)` class: *"A CONSUMER IS TESTED AGAINST A PAYLOAD ITS PUBLISHER
BUILT. Never hand-write a fixture that 'looks like' the payload."* So these
tests drive `bot_learn`'s REAL `_save_state` and read what it actually handed to
the store — a hand-built `{"updated": ...}` fixture would have passed against
the broken code and is exactly how this survived.
"""
import importlib
import sys
import types
from datetime import datetime, timedelta, timezone

import pytest

pytestmark = pytest.mark.autonomy

import fleet_immune as FI          # noqa: E402


# ---------------------------------------------------------------------------
# 1 · the PUBLISHER really emits the field the consumer reads
# ---------------------------------------------------------------------------

def _capture_brain_write(monkeypatch):
    """Drive the real `bot_learn._save_state` and return what it stored."""
    import bot_learn as BL

    written = {}
    shim = types.ModuleType("bot_pnl_store")

    def save_state(key, payload):
        written[key] = payload
        return True

    shim.save_state = save_state
    real = sys.modules.get("bot_pnl_store")
    sys.modules["bot_pnl_store"] = shim
    try:
        BL._save_state({"runs": 337, "hypotheses": {}})
    finally:
        if real is None:
            sys.modules.pop("bot_pnl_store", None)
        else:
            sys.modules["bot_pnl_store"] = real
    return written


def test_the_brain_memory_payload_carries_an_updated_stamp(monkeypatch):
    written = _capture_brain_write(monkeypatch)
    assert "learning-brain" in written, "the brain never wrote its memory"
    payload = written["learning-brain"]
    assert "updated" in payload, (
        "`learning-brain` carries no `updated` stamp, so brain_amnesia — I2's "
        f"declared enforcement — cannot compute its skew. Keys: {sorted(payload)}")
    # the fleet's own bus contract, which this key alone never honoured
    assert "ttl_sec" in payload
    ts = datetime.fromisoformat(str(payload["updated"]))
    assert abs((datetime.now(timezone.utc) - ts).total_seconds()) < 300


def test_the_stamp_is_written_before_the_save_so_a_failed_save_keeps_the_old_one():
    """The signal depends on the ORDER. Stamping before the write means a
    failed save leaves the stored row on its OLD stamp, so the skew against
    fresh vitals grows exactly as the amnesia does. Stamping after a successful
    write would refresh the mark on the very cycle that lost the memory."""
    import bot_learn as BL

    state = {"runs": 1}
    shim = types.ModuleType("bot_pnl_store")
    seen = {}

    def save_state(key, payload):
        seen["at_write"] = dict(payload)
        return False                      # the failure this detector exists for

    shim.save_state = save_state
    real = sys.modules.get("bot_pnl_store")
    sys.modules["bot_pnl_store"] = shim
    try:
        BL._save_state(state)
    finally:
        if real is None:
            sys.modules.pop("bot_pnl_store", None)
        else:
            sys.modules["bot_pnl_store"] = real
    assert "updated" in seen["at_write"], (
        "the stamp must exist at the moment of the write, not after it")


# ---------------------------------------------------------------------------
# 2 · the CONSUMER fires on the real shape
# ---------------------------------------------------------------------------

def _iso(dt):
    return dt.isoformat(timespec="seconds")


def test_it_fires_on_the_measured_incident(monkeypatch):
    """The (hx) incident, reproduced through the real publisher's shape:
    memory three days behind fresh vitals, with the run counter lagging by
    exactly 1 — which is what correct write-after-publish ordering looks like
    forever, and why the counter version fired nothing."""
    written = _capture_brain_write(monkeypatch)
    brain = dict(written["learning-brain"])
    now = datetime.now(timezone.utc)
    brain["updated"] = _iso(now - timedelta(hours=71.4))
    brain["runs"] = 337
    vitals = {"updated": _iso(now), "run": 338}

    out = FI.brain_amnesia(brain, vitals)
    assert out, "the memory is 71.4h behind fresh vitals and nothing fired"
    assert out[0]["organ"] == "learning-brain"
    assert "MEMORY NOT PERSISTING" in out[0]["detail"]
    assert "337" in out[0]["detail"] and "338" in out[0]["detail"]


def test_a_healthy_brain_stays_silent(monkeypatch):
    """The control group. A detector that fires on everything trains the
    operator to ignore it."""
    written = _capture_brain_write(monkeypatch)
    brain = dict(written["learning-brain"])
    now = datetime.now(timezone.utc)
    brain["updated"] = _iso(now - timedelta(minutes=2))
    assert FI.brain_amnesia(brain, {"updated": _iso(now), "run": 5}) == []


def test_the_constant_lag_of_one_is_not_itself_a_signal(monkeypatch):
    """I2's actual lesson: runs=337 vs run=338 is byte-identical to healthy
    ordering. Only the timestamp distinguishes them, so a fresh memory with the
    same counter lag must stay quiet."""
    written = _capture_brain_write(monkeypatch)
    brain = dict(written["learning-brain"])
    now = datetime.now(timezone.utc)
    brain["updated"] = _iso(now)
    brain["runs"] = 337
    assert FI.brain_amnesia(brain, {"updated": _iso(now), "run": 338}) == []


# ---------------------------------------------------------------------------
# 3 · a BLIND detector must say so, not read as healthy
# ---------------------------------------------------------------------------

def test_a_memory_with_no_stamp_reports_that_it_cannot_tell():
    """The exact production state before this fix — and it read as CLEAN."""
    now = _iso(datetime.now(timezone.utc))
    out = FI.brain_amnesia({"runs": 337, "hypotheses": {}}, {"updated": now})
    assert out, (
        "an unstamped memory payload made this guard return [] — "
        "indistinguishable from a healthy brain, which is how I2's "
        "enforcement stayed inert")
    assert "BLIND" in out[0]["detail"]
    # it must NOT claim amnesia — it cannot know that
    assert "MEMORY NOT PERSISTING" not in out[0]["detail"]


def test_a_booting_brain_with_no_memory_row_stays_quiet():
    """Fail-safe quiet is still right where the silence is informative: an
    empty payload is a brain that has not written yet, not a blind guard."""
    now = _iso(datetime.now(timezone.utc))
    assert FI.brain_amnesia({}, {"updated": now}) == []
    assert FI.brain_amnesia(None, {"updated": now}) == []


def test_dark_vitals_stay_quiet():
    """Nothing to compare against — a dark bus must not page anyone."""
    old = _iso(datetime.now(timezone.utc) - timedelta(days=3))
    assert FI.brain_amnesia({"runs": 1, "updated": old}, {}) == []
    assert FI.brain_amnesia({"runs": 1, "updated": old}, None) == []


# ---------------------------------------------------------------------------
# 4 · the wiring: the key must be in the organ's fetch list
# ---------------------------------------------------------------------------

def test_learning_brain_is_in_the_immune_fetch_list():
    """Without the key the scanner is dead code — the registered-but-inert
    shape this organ has already been bitten by twice ((hh), the churn counter).
    """
    import ast
    import pathlib
    src = pathlib.Path(FI.__file__).read_text()
    tree = ast.parse(src)
    keys = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
                getattr(t, "id", "") == "_keys" for t in node.targets):
            for c in ast.walk(node.value):
                if isinstance(c, ast.Constant) and isinstance(c.value, str):
                    keys.add(c.value)
    assert keys, "could not find the immune organ's _keys tuple — scan is blind"
    assert "learning-brain" in keys and "brain-vitals" in keys, sorted(keys)
