"""[2026-08-20 (ry)] FOUR DECLARED ENFORCEMENTS THAT EXISTED AND DID NOTHING.

Harvested from PR #153, a branch that can never merge (no merge base with main
— main's history was rebuilt under it), whose diff was nonetheless right. Each
test here pins a mechanism that was INERT on main while every guard around it
reported green, because the guards check that a declared enforcement EXISTS,
never that it WORKS — the caveat at the top of CLAUDE.md, realised four times.

The shape they share: a failure path that returns quietly. A swallowed
NameError, a `return []` on an unreadable stamp, a lookup that cannot match, a
`sys.exit` in a test. None of them raised, so none of them were noticed.
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from datetime import datetime, timedelta, timezone  # noqa: E402

import bot_pnl_store as store  # noqa: E402
import fleet_immune as fi  # noqa: E402


# --- 1 · the organ death recorder must actually reach storage --------------
def test_record_organ_error_reaches_save_state(monkeypatch):
    """It returned False without ever calling save_state, because `datetime`
    is not module-level in bot_pnl_store and the local import was missing, so
    every call raised NameError into a blanket `except: return False`.

    Asserting the RETURN VALUE alone would not have caught it — False is also
    what a dark DB returns. The test counts the write."""
    seen = {"save": 0}

    def _save(key, payload):
        seen["save"] += 1
        seen["payload"] = payload
        return True

    monkeypatch.setattr(store, "load_state", lambda k: {})
    monkeypatch.setattr(store, "save_state", _save)

    ok = store.record_organ_error("test-organ", ValueError("boom"), "f.py:1")
    assert seen["save"] == 1, "record_organ_error never reached save_state"
    assert ok is True, "a committed write must report True"
    p = seen["payload"]
    assert p["healthy"] is False
    assert "ValueError" in p["error"] and "boom" in p["error"]
    assert p["error_at"], "the timestamp is the field whose import was missing"


def test_organ_main_does_not_claim_a_record_it_did_not_make(monkeypatch, capsys):
    """I4 + I8 in four lines: the caller discarded the result and printed
    'ORGAN FAULT recorded ... so the immune organ can see it' unconditionally —
    false on every call while the recorder was broken, and false again any time
    the DB is down. The two outcomes must read differently."""
    monkeypatch.setattr(store, "record_organ_error", lambda *a, **k: False)

    def _boom():
        raise RuntimeError("organ died")

    rc = store.organ_main("test-organ", _boom)
    assert rc == 1
    err = capsys.readouterr().err
    assert "COULD NOT BE RECORDED" in err, (
        "a failed record must say so — otherwise the log asserts a page that "
        "will never arrive")

    monkeypatch.setattr(store, "record_organ_error", lambda *a, **k: True)
    store.organ_main("test-organ", _boom)
    err2 = capsys.readouterr().err
    assert "recorded on its own bot_state key" in err2
    assert "COULD NOT BE RECORDED" not in err2


# --- 2 · I2's amnesia check must not be blind ------------------------------
# Timestamps are COMPUTED, never literals: a date the era tables own would make
# a legitimate table move redden a test that is not about dates at all
# (audit_era_date_literals caught exactly that on this file's first draft).
_NOW = datetime.now(timezone.utc)
_VIT = {"run": 338, "updated": _NOW.isoformat()}


def test_brain_amnesia_reports_when_it_cannot_see():
    """The brain's blob carries no stamp (save_state writes the COLUMN;
    fetch_states selects only (bot, state)), so `bt` was None on every real
    cycle and this returned [] forever while reading as healthy."""
    for blob in ({"runs": 337}, {"updated": "nope"}):
        out = fi.brain_amnesia(blob, _VIT)
        assert out, f"a memory row with no readable stamp must not be silent: {blob}"
        assert "BLIND" in out[0]["detail"]
        # ...and it must not overclaim: blindness is not a diagnosis of amnesia
        assert "NOT a claim that the brain is amnesiac" in out[0]["detail"]


def test_brain_amnesia_stays_quiet_where_silence_is_informative():
    """The fix must not turn a booting brain or a dark bus into a page."""
    assert fi.brain_amnesia({}, _VIT) == [], "no memory row yet — a booting brain"
    assert fi.brain_amnesia({"runs": 337, "updated": _VIT["updated"]}, {}) == [], \
        "nothing to compare against — a dark bus"
    assert fi.brain_amnesia(None, None) == []


def test_brain_amnesia_still_detects_real_amnesia():
    """The original detector must survive the blindness fix."""
    stale = (_NOW - timedelta(hours=72)).isoformat()
    out = fi.brain_amnesia({"runs": 337, "updated": stale}, _VIT)
    assert out and "MEMORY NOT PERSISTING" in out[0]["detail"]


def test_the_brain_stamps_the_blob_it_saves():
    """The other half — without a stamp INSIDE the payload, the detector above
    can only ever report blindness. Pinned at the source so a future refactor
    cannot quietly drop it."""
    src = (ROOT / "bot_learn.py").read_text()
    assert 'state["updated"]' in src, (
        "bot_learn must stamp `updated` into the blob; the bot_state column is "
        "invisible to fetch_states, which is what every organ reads")


# --- 3 · I10's real-money gate must ask with the key the publisher writes ---
def test_golive_gate_asks_with_the_row_id_not_the_bare_base():
    """`golive-readiness.books` is keyed by the ledger's bot column. Verified
    against the live payload: it holds `perps-funding-spread-lshadow` and no
    bare base, so `golive_blocker(BOT)` could never match and I10's gate was
    structurally unpassable — fail-closed, but unpassable."""
    src = (ROOT / "lighter_funding_spread_bot.py").read_text()
    assert "_why = golive_blocker(ctx.bot_id)" in src, (
        "the live gate must look up the suffixed row id")
    assert "_why = golive_blocker(BOT)" not in src


def test_golive_gate_admits_a_ready_book_and_refuses_an_absent_one(monkeypatch):
    """Drives the real gate with a payload keyed the way the real publisher
    keys it — the (hj) rule, which is exactly what the old selftest violated."""
    import os
    import lighter_funding_spread_bot as fs
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).timestamp()
    fresh = datetime.fromtimestamp(now - 60, timezone.utc).isoformat()
    row = fs.BOT + "-lshadow"
    payload = {"updated": fresh,
               "books": {row: {"ready": True, "bars_passed": 6,
                               "bars": {b: True for b in
                                        ("window", "closes", "mean", "t",
                                         "halves", "maxdd")}}}}
    monkeypatch.setitem(os.environ, "FUNDSPREAD_GOLIVE", "1")
    assert fs.golive_blocker(row, payload, now) is None, \
        "a READY book with the opt-in must be admitted"
    # the bare base is what the bug asked for — it must still find nothing,
    # which is the proof the two spellings are different books
    assert fs.golive_blocker(fs.BOT, payload, now), \
        "the bare base must not resolve — the suffix distinguishes two books"


# --- 4 · a selftest may not exit before its assertions --------------------
def test_regime_oracle_selftest_does_not_kill_itself():
    """A copy-pasted `sys.exit(store.organ_main(...))` sat inside _selftest and
    raised SystemExit(0), so 39 assertions below never ran while
    tests/test_selftests.py — which checks only the exit code — called it
    PASSING."""
    src = (ROOT / "regime_oracle.py").read_text()
    body = src[src.index("def _selftest"):]
    # CODE ONLY — a page-wide substring scan is not a structural claim, and
    # this file's own explanatory comment quotes the very line it forbids.
    code = "\n".join(ln for ln in body.splitlines()
                     if not ln.lstrip().startswith("#"))
    assert "sys.exit(store.organ_main(" not in code, (
        "a selftest that exits cannot assert; keep the process and check rc")
    assert "_rc = store.organ_main(" in code
    assert "main() published NOTHING" in code, (
        "un-deadening assertions needs a guard that the fixture still drives "
        "the organ — this one caught a second defect on its first run")
