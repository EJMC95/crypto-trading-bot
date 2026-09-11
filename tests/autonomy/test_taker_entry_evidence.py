"""[(aao)] THE ENTRY CAPTURE WAS SIX FIELDS WIDE AND THE TICKET IS ELEVEN.

`(di)` captured `brk_quality`/`up_strength` at the entry site "so winning
criteria can be DERIVED from realized closes", and recorded what the gap had
already cost: *"the first 6 breakoutup closes shipped without their features
(unrecoverable from the ledger)."* The same defect was still there one turn
later, on different fields.

Measured 2026-09-11 over 8.3 days of scout tape (2,768 ticket episodes):
**every lens publishes `regime`** — the per-asset oracle verdict,
`{"dir": ±1|0, "v": "LONG-window"|"SHORT-window"|"dir-flat"|"chop-gated"}` —
and **not one of the taker's 304 closes carries it.** That is the single
conditioning variable item 18 says this fleet most needs: the whole Lighter
tape is one falling-BTC regime, so a directional grade is a grade in that
regime only, and 41 days of closes cannot answer the question. `noncrypto`
rides every lens, `trend` rides dip, and the divergence apr pair is that
lens's entire thesis. All were dropped at `ev = {...}`.

OBSERVABLE-ONLY, and the three refusals are asserted below: the merge is by
setdefault so evidence can never clobber `bars`/`bars_basis`/`policy`; no
decision reads these; and the SIX ORIGINAL KEYS keep their exact prior payload
shape, so no existing consumer's `in extra` test changes meaning.

`side` is deliberately NOT captured — the close tag already carries it, and a
second spelling of a field graders key on is the (xe) trap.
"""
import ast
import os
import pathlib

import pytest

pytestmark = pytest.mark.autonomy

import sys
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("TT_BULL_MODE", "on")

import lighter_ticket_taker as tt                              # noqa: E402

#: what the scout actually publishes, measured off the live tape
TICKET = {"sym": "AAA", "range_pos": 0.97, "chg_pct": 4.2, "vol_m": 2.7,
          "prem_bps": 0.8, "apr_pct": 10.5, "noncrypto": False,
          "regime": {"dir": 1, "v": "LONG-window"}, "trend": "up_v1",
          "lighter_apr": 12.0, "xvenue_apr": 9.5, "side": "short"}

NEW = ("regime", "noncrypto", "trend", "lighter_apr", "xvenue_apr")
OLD = ("range_pos", "chg_pct", "vol_m", "prem_bps", "apr_pct", "gap_pct")


def _ev_source():
    src = (ROOT / "lighter_ticket_taker.py").read_text()
    return ast.parse(src), src


def test_the_six_original_keys_are_still_captured_verbatim():
    """DRIVEN, not grepped. Their payload shape must not move: consumers
    already test `in extra` on them, and a breakout ticket with no gap_pct
    must still stamp `gap_pct: null`.

    Mutation: drop any of the six from EV_KEYS_BASE => red.
    """
    ev = tt.entry_evidence(TICKET)
    for k in OLD:
        assert k in ev, f"{k} dropped from the entry capture: {ev}"
    bare = tt.entry_evidence({"sym": "AAA"})
    assert set(bare) == set(OLD) and bare["gap_pct"] is None, bare


def test_the_regime_verdict_reaches_the_close_row():
    """THE point of the entry, driven end to end: ticket -> entry_evidence ->
    _close_extra. Mutation: drop "regime" from EV_KEYS_ADDED => red."""
    out = tt._close_extra({"bars": {"tp": 0.04, "sl": -0.07, "max_hold_h": 24},
                           "evidence": tt.entry_evidence(TICKET)})
    assert out["regime"] == {"dir": 1, "v": "LONG-window"}, out


@pytest.mark.parametrize("key", NEW)
def test_each_new_field_reaches_the_close_extra(key):
    """Driven through the REAL `_close_extra`, not grepped — the (di) failure
    was that the capture stopped short of the ledger row."""
    out = tt._close_extra({"bars": {"tp": 0.04, "sl": -0.07,
                                    "max_hold_h": 24},
                           "evidence": tt.entry_evidence(TICKET)})
    assert out[key] == TICKET[key], out


def test_side_is_deliberately_not_captured():
    """The tag carries it. A second spelling of a field graders key on is the
    (xe) one-position-two-spellings trap. The TICKET carries side='short';
    the evidence must not."""
    assert TICKET["side"] == "short"
    assert "side" not in tt.entry_evidence(TICKET)


def test_evidence_can_never_clobber_the_bars_or_policy_stamp():
    """The three refusals. Mutation: swap `_close_extra`'s setdefault merge
    for a plain update => red."""
    bars = {"tp": 0.04, "sl": -0.07, "max_hold_h": 24}
    out = tt._close_extra({"bars": bars, "evidence": {
        "bars": "EVIL", "bars_basis": "EVIL", "policy": "EVIL",
        "regime": {"dir": 1, "v": "LONG-window"}}})
    assert out["bars"] == bars and out["bars_basis"] == "entry"
    assert out["policy"] != "EVIL"
    assert out["regime"] == {"dir": 1, "v": "LONG-window"}


def test_an_absent_new_field_is_omitted_not_stamped_null():
    """Absent is UNKNOWN — the convention `peak_ret`/`give_back` already use,
    and the reason a grader must not read a missing regime as 'no regime'.
    Mutation: stamp None for a missing key => red."""
    thin = {k: TICKET[k] for k in ("sym", "range_pos", "chg_pct", "vol_m",
                                   "prem_bps", "apr_pct")}
    thin["regime"] = {"dir": 0, "v": "dir-flat"}   # trend/apr pair absent
    out = tt._close_extra({"bars": {"tp": 0.04, "sl": -0.07,
                                    "max_hold_h": 24},
                           "evidence": tt.entry_evidence(thin)})
    assert "trend" not in out and "lighter_apr" not in out, out
    assert out["regime"]["v"] == "dir-flat"


def test_the_capture_changes_no_decision():
    """Observable-only. The entry site must only ever WRITE `ev` into
    meta/raw, never branch on it."""
    _tree, src = _ev_source()
    i = src.index("ev = entry_evidence(t)")
    after = src[i:i + 4000]
    for bad in ("if ev", "if not ev", "ev.get("):
        assert bad not in after, f"the evidence dict is being READ: {bad!r}"


def test_the_call_site_ASKS_the_owner_and_never_rebuilds_the_dict():
    """The mutation that survived round one: an inline dict comprehension in
    `main()` is not reachable by a test that builds the dict itself. The call
    site must CALL `entry_evidence`.

    Mutation: inline the comprehension again at the call site => red.
    """
    tree, _src = _ev_source()
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "main")
    calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call)
             and getattr(n.func, "id", None) == "entry_evidence"]
    assert calls, "main() no longer asks entry_evidence for the capture"
    assigns = [n for n in ast.walk(fn) if isinstance(n, ast.Assign)
               and len(n.targets) == 1
               and getattr(n.targets[0], "id", None) == "ev"]
    assert assigns and all(isinstance(a.value, ast.Call) for a in assigns), \
        "the entry site must CALL the owner, never rebuild the dict inline"
