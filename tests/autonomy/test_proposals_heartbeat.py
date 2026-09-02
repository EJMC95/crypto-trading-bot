"""[2026-09-02 (wy)] AN EMPTY CHANNEL MUST NOT READ AS A DEAD ONE.

`fleet_proposals` promised that "the resting state is an empty channel" — and
`propose()` writes only when a stance survives, so the moment every proposer
had nothing to say the key stopped being written and aged past its 2h TTL.
Measured on the organ board 2-Sep 09:06Z: `tuning_proposals` DARK at 3.8h with
the sentinel, the shortfall organ and respiration all alive and quiet. I1/I13:
"nobody is proposing" and "nobody is writing" were byte-identical.

The fix is `heartbeat()` — the same locked merge with an empty stance set —
called by the sentinel (the 10-min proposer) whenever it proposed nothing.
These pins turn red under: dropping the heartbeat call from the sentinel;
a heartbeat that forgets other authors' live entries; a heartbeat that keeps
expired ones; the board grading a fresh-empty channel as anything but idle.
"""
import copy
import importlib.util
import os
import sys
import time
from datetime import datetime, timezone

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import fleet_proposals as fp   # noqa: E402

pytestmark = pytest.mark.autonomy

_spec = importlib.util.spec_from_file_location(
    "organ_board", os.path.join(ROOT, "scripts", "organ_board.py"))
OB = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("organ_board", OB)
_spec.loader.exec_module(OB)


def _entry(lever, set_by, expires_ts, value=5.0):
    return {"lever": lever, "value": value, "direction": "restrict",
            "set_by": set_by, "expires": fp._iso(expires_ts)}


def test_heartbeat_restamps_and_keeps_only_live_entries_of_every_author():
    now = time.time()
    prev = {"updated": fp._iso(now - 9000), "ttl_sec": 7200, "proposals": {
        "brain:taker.momo_chg": _entry("taker.momo_chg", "brain", now + 600),
        "impl-shortfall:taker.brk_range": _entry("taker.brk_range", "impl-shortfall", now - 60, 0.9),
    }}
    assert not fp._is_fresh(prev, now)                       # the measured state
    hb = fp._merged(prev, {}, now, float(fp.TTL_SEC))
    assert fp._is_fresh(hb, now)
    assert hb["updated"] == fp._iso(now)
    assert set(hb["proposals"]) == {"brain:taker.momo_chg"}   # live kept, expired dropped
    assert hb["proposals"]["brain:taker.momo_chg"]["set_by"] == "brain"


class _Store:
    """A minimal bot_pnl_store stand-in: no locked update, plain load/save."""
    def __init__(self, prev=None, ok=True):
        self.prev, self.ok, self.saved = prev, ok, []

    def load_state(self, key):
        return copy.deepcopy(self.prev)

    def save_state(self, key, payload):
        self.saved.append((key, payload))
        return self.ok


def test_heartbeat_writes_a_fresh_empty_channel(monkeypatch):
    now = time.time()
    st = _Store(prev={"updated": fp._iso(now - 9000), "ttl_sec": 7200, "proposals": {}})
    monkeypatch.setattr(fp, "store", st)
    out = fp.heartbeat("event-sentinel", now_ts=now)
    assert out is not None and out["proposals"] == {} and out["updated"] == fp._iso(now)
    assert st.saved and st.saved[0][0] == fp.KEY
    # a failed durable write is reported as None, never as a phantom payload
    monkeypatch.setattr(fp, "store", _Store(prev={}, ok=False))
    assert fp.heartbeat("event-sentinel", now_ts=now) is None
    monkeypatch.setattr(fp, "store", None)
    assert fp.heartbeat("event-sentinel", now_ts=now) is None


def test_the_board_reads_a_fresh_empty_channel_as_idle_and_a_stale_one_as_dark():
    bus = copy.deepcopy(OB.FIXTURE_BUS)
    now = OB.FIXTURE_NOW
    bus["tuning_proposals"] = {"updated": (now.isoformat() if hasattr(now, "isoformat")
                                           else datetime.fromtimestamp(now, tz=timezone.utc).isoformat()),
                               "ttl_sec": 7200, "proposals": {}}
    rows = {r["organ"]: r for r in OB.grade(bus, OB.FIXTURE_PNL, now)}
    assert rows["tuning_proposals"]["state"] == "idle", rows["tuning_proposals"]
    # the pre-heartbeat state: nothing wrote the key, so it aged out -> dark
    bus["tuning_proposals"]["updated"] = "2026-09-01T00:00:00+00:00"
    rows = {r["organ"]: r for r in OB.grade(bus, OB.FIXTURE_PNL, now)}
    assert rows["tuning_proposals"]["state"] == "dark", rows["tuning_proposals"]


def test_the_sentinel_heartbeats_when_it_proposes_nothing():
    with open(os.path.join(ROOT, "event_sentinel.py")) as fh:
        src = fh.read()
    body = src.split("proposals_for(_bias, active", 1)[1].split("SELF-TUNING", 1)[0]
    assert 'fprop.heartbeat("event-sentinel"' in body, \
        "the sentinel must re-stamp the channel on a cycle with nothing to propose"
    assert "if _wrote is None" in body, \
        "the heartbeat must also cover a propose() that wrote nothing (every entry dropped)"
