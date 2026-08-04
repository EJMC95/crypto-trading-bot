"""[2026-08-04 (jf)] THE GRADER CONSUMES THE POLICY STAMP THE LEDGER CARRIES.

THE GAP THIS CLOSES: `lighter-ticket-taker-lighter` — REAL MONEY — changed
policy on 24-Jul (TT_BULL_MODE), 29-Jul and 30-Jul ((hj)'s LIVE_SIDES hard
gate), and (hm) rules that a sample pooled across a policy change is
meaningless. Every taker close has stamped `extra.policy` since (fx)/(gi)/(hj)
— written precisely so "any grader can split eras MECHANICALLY" — and no
grader ever consumed it: `golive_readiness`'s era for the taker sat at the
single 17-Jul accrual date, so its t/halves bars graded a mixture of three
policies.

Measured on the live ledger the day this shipped: the live row's 38 closes are
25 unstamped (the three-policy mixture) + a 13-close run stamped
{bull, lenses:[divergence], sides:{divergence:[short]}, venue:lighter_live}
since 2026-07-30T11:05:43Z — so the graded era starts there, and the earliest
gradeable date (~29-Aug) is computed from the real boundary.

EVERY STAMP IN THIS FILE IS BUILT BY THE PUBLISHER — `lighter_ticket_taker.
_close_extra`, the function that writes the ledger's close rows — never by a
hand-written fixture. (hj): four consumers died in one session reading keys
their publishers do not emit, each with a GREEN selftest, because the fixture
was written by whoever wrote the consumer. Policy changes are simulated by
setting the taker's own module globals (BULL_MODE, TT_VENUE, MAX_OPEN), so the
stamp SHAPE is always the real one.
"""
import contextlib
import datetime as _dt
import pathlib
import sys

import pytest

pytestmark = pytest.mark.autonomy

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "scripts"))

import golive_readiness as g          # noqa: E402
import lighter_ticket_taker as tt     # noqa: E402

LIVE = "lighter-ticket-taker-lighter"
UTC = _dt.timezone.utc


@contextlib.contextmanager
def taker_policy(**over):
    """Set the taker's own module globals for the duration — the stamp is then
    built by the real `_close_extra` under a real policy state."""
    saved = {k: getattr(tt, k) for k in over}
    try:
        for k, v in over.items():
            setattr(tt, k, v)
        yield
    finally:
        for k, v in saved.items():
            setattr(tt, k, v)


def close_extra(**policy):
    with taker_policy(**policy):
        return tt._close_extra({})


def _row(open_dt, close_dt, extra):
    return (0.01, 10.0, close_dt,
            open_dt.isoformat() if open_dt else None, extra)


def _at(day, hour=0, minute=0):
    return _dt.datetime(2026, 8, day, hour, minute, tzinfo=UTC)


# ---------------------------------------------------------------------------
# 1. The publisher's stamp is readable by the grader — the contract itself.
# ---------------------------------------------------------------------------

def test_the_publishers_stamp_is_readable_by_the_grader():
    sig = g.policy_signature(close_extra(TT_VENUE="lighter_live"))
    assert sig is not None, (
        "the grader cannot read the stamp the taker actually writes — the "
        "whole (jf) mechanism is dark")
    import json
    pol = json.loads(sig)
    # the DIFFERENT-IN-KIND fields, from the taker's own hard gates
    assert pol["lenses"] == sorted(tt.allowed_lenses("lighter_live"))
    assert pol["sides"] == {"divergence": ["short"]}, (
        "the live stamp's side map must come from allowed_sides — the (hj) "
        "hard gate, which IS the policy")


def test_the_shadow_stamp_reads_differently_from_the_live_one():
    """Venue mode is policy: the two arms must never pool into one era."""
    live = g.policy_signature(close_extra(TT_VENUE="lighter_live"))
    shadow = g.policy_signature(close_extra(TT_VENUE="lighter_shadow"))
    assert live != shadow


# ---------------------------------------------------------------------------
# 2. The boundary: first close of the newest same-policy run, keyed on OPEN.
# ---------------------------------------------------------------------------

def _bull_flip_rows():
    """The 24-Jul incident shape, rebuilt through the publisher: a run under
    BULL_MODE off, then a run under BULL_MODE on. One straddler opened in the
    ambiguity window."""
    off = close_extra(TT_VENUE="lighter_live", BULL_MODE=False)
    on = close_extra(TT_VENUE="lighter_live", BULL_MODE=True)
    return [
        _row(_at(1, 0), _at(1, 6), off),
        _row(_at(1, 6), _at(1, 12), off),
        _row(_at(2, 0), _at(2, 6), off),
        _row(_at(2, 20), _at(3, 6), on),     # run start — itself a straddler
        _row(_at(3, 6), _at(3, 12), on),
        _row(_at(3, 12), _at(3, 18), on),
    ]


def test_a_real_policy_flip_creates_the_boundary_at_the_first_new_close():
    rows = _bull_flip_rows()
    ep, iso, pol, n = g.stamped_policy_boundary(rows)
    assert n == 3 and pol["bull"] is True, (n, pol)
    assert ep == _at(3, 6).timestamp(), (
        "the boundary must be the FIRST close of the newest run — an upper "
        "bound on when the change landed; the last old close would be the "
        "generous bound and can smuggle old-policy trades in")


def test_the_era_is_keyed_on_the_open_so_straddlers_are_out():
    rows = _bull_flip_rows()
    d = g.era_rows(LIVE, rows, detail=True)
    assert d["source"] == "policy-stamp"
    # the run-start row OPENED before its own close (the boundary), so it and
    # everything earlier is out; only the two cleanly-in-era rows count.
    assert len(d["scoped"]) == 2 and len(d["all_time"]) == 6, d["scoped"]
    assert {r[2] for r in d["scoped"]} == {_at(3, 12), _at(3, 18)}


def test_the_stamp_boundary_supersedes_the_declared_era_by_max():
    """The taker's declared era is the 17-Jul accrual date; the stamps are
    later, so they govern — and the declaration is still published beside the
    verdict rather than discarded (an era is the LATEST of every invalidating
    change; the earlier reason keeps covering everything before it)."""
    d = g.era_rows(LIVE, _bull_flip_rows(), detail=True)
    assert d["declared_since"] == g.POLICY_ERA["lighter-ticket-taker"][0]
    assert d["iso"] == d["stamp_since"] and d["source"] == "policy-stamp"


# ---------------------------------------------------------------------------
# 3. Ordinary tuning must NOT reset the clock ((hc) — anti-weaponisation).
# ---------------------------------------------------------------------------

def test_a_max_open_move_is_not_a_policy_boundary():
    """`max_open` rides the same stamp but is a capacity lever. If it reset
    the era, every growth-rail walk would keep the 30-day clock at zero and
    the gate would be unreachable forever."""
    a = close_extra(TT_VENUE="lighter_live", MAX_OPEN=2)
    b = close_extra(TT_VENUE="lighter_live", MAX_OPEN=9)
    assert a["policy"]["max_open"] != b["policy"]["max_open"], (
        "fixture broke: the publisher no longer stamps max_open")
    assert g.policy_signature(a) == g.policy_signature(b), (
        "a capacity lever move changed the policy signature — POLICY_SIG_FIELDS "
        "has grown a tuning field, which weaponises the era ((hc))")
    rows = [_row(_at(1, 0), _at(1, 6), a), _row(_at(1, 6), _at(1, 12), b)]
    assert g.stamped_policy_boundary(rows)[0] is None


# ---------------------------------------------------------------------------
# 4. THE (ij) RULING — the veto does not reach the stamp, structurally.
# ---------------------------------------------------------------------------

def test_the_lens_veto_is_not_consulted_by_the_stamp():
    """The (jf) ruling that the 1-Aug veto rewrite does NOT reset the live
    taker's clock rests on a code fact: the stamp's lens/side sets are the
    hard gates (`allowed_lenses` is "deliberately NOT the brain's veto"), so
    a veto flip cannot move the stamped policy. Pinned by making every veto
    entry point explode: if a future edit wires the veto into the stamp, the
    stamp build raises here and the ruling has to be re-argued, not silently
    invalidated."""
    def _boom(*a, **k):
        raise AssertionError("the policy stamp consulted the lens veto")
    with taker_policy(vetoed_lenses=_boom, realised_lens_evidence=_boom,
                      lens_loses=_boom):
        extra = close_extra(TT_VENUE="lighter_live")
    assert g.policy_signature(extra) is not None


# ---------------------------------------------------------------------------
# 5. Fail-closed on unreadable stamps.
# ---------------------------------------------------------------------------

def test_an_unreadable_stamp_breaks_the_run():
    rows = _bull_flip_rows()
    corrupt = dict(rows[4][4], policy="junk")          # mid-run, unreadable
    rows[4] = rows[4][:4] + (corrupt,)
    ep, _iso, _pol, n = g.stamped_policy_boundary(rows)
    assert n == 1 and ep == _at(3, 18).timestamp(), (
        "an unreadable stamp must break the run — the boundary moves LATER, "
        "never earlier, because a trade whose policy cannot be confirmed is "
        "exactly the credit the era withdraws")


def test_a_stampless_ledger_derives_nothing_and_the_declared_era_stands():
    """Every non-stamping book in the fleet — the (jf) change must be a
    byte-level no-op for all of them."""
    rows = [_row(_at(1, 0), _at(1, 6), {}), _row(_at(1, 6), _at(1, 12), None)]
    assert g.stamped_policy_boundary(rows) == (None, None, None, 0)
    d = g.era_rows(LIVE, rows, detail=True)
    assert d["source"] == "declared"
    assert d["iso"] == g.POLICY_ERA["lighter-ticket-taker"][0]
    # and the pre-(jf) 3-tuple contract is intact for existing callers
    t3 = g.era_rows(LIVE, rows)
    assert isinstance(t3, tuple) and len(t3) == 3 and t3[2] == d["iso"]


# ---------------------------------------------------------------------------
# 6. End to end through the REAL main(): the published payload says which
#    policy the graded sample is, and the report line names the source.
# ---------------------------------------------------------------------------

def test_main_publishes_the_policy_era(capsys, monkeypatch):
    import bot_pnl_store as store
    old = close_extra(TT_VENUE="lighter_live", BULL_MODE=False)
    new = close_extra(TT_VENUE="lighter_live", BULL_MODE=True)

    def _iso(day, hour):
        return _at(day, hour).isoformat()

    rows = []
    # six closes under the old policy — all opened AFTER the declared 17-Jul
    # era, so under declared-only scoping every one of them would count. That
    # is what makes the assertion below discriminating.
    for i in range(6):
        rows.append({"bot": LIVE, "profit_abs": 2.0, "profit_ratio": 0.01,
                     "open_ts": _iso(1 + i, 0), "close_ts": _iso(1 + i, 6),
                     "extra": old})
    # one straddler (opened before the boundary, stamped new at close), then
    # four cleanly in-era closes.
    rows.append({"bot": LIVE, "profit_abs": 2.0, "profit_ratio": 0.01,
                 "open_ts": _iso(8, 0), "close_ts": _iso(10, 6), "extra": new})
    for i in range(4):
        rows.append({"bot": LIVE, "profit_abs": 2.0, "profit_ratio": 0.01,
                     "open_ts": _iso(10, 6 + i), "close_ts": _iso(11, 6 + i),
                     "extra": new})
    saved = {}
    monkeypatch.setattr(store, "fetch_paper_trades", lambda limit=2000: rows)
    monkeypatch.setattr(store, "save_state", lambda k, v: saved.setdefault(k, v))
    monkeypatch.setattr(store, "save_history", lambda k, v: True)
    monkeypatch.setattr(sys, "argv", ["golive_readiness.py", "--min-closes", "5",
                                      "--publish"])
    g.main()
    out = capsys.readouterr().out
    assert "(policy-stamp)" in out, (
        "the report line must name the boundary's source — a date the "
        "POLICY_ERA table does not contain must not read as declared:\n" + out)
    assert "4 of 11 closes count" in out, out

    era = saved["golive-readiness"]["books"][LIVE]["era"]
    assert era["source"] == "policy-stamp"
    assert era["since"] == era["stamp_since"] == _at(10, 6).isoformat()
    assert era["declared_since"] == g.POLICY_ERA["lighter-ticket-taker"][0]
    assert era["policy"]["lenses"] == ["divergence"]
    assert era["policy"]["sides"] == {"divergence": ["short"]}, (
        "the payload must say WHICH policy the graded sample is — that is how "
        "the ~29-Aug gradeable date stops being hand-waved")
    assert era["closes_in_era"] == 4 and era["closes_all_time"] == 11


def test_integrity_blocking_runs_over_the_same_era(capsys, monkeypatch):
    """[(ii)] The blocking integrity check runs over the GRADED sample. A
    same-pair overlap wholly under the OLD policy must not veto the new-policy
    era — it is reported as historical, exactly like a pre-declared-era one."""
    import bot_pnl_store as store
    old = close_extra(TT_VENUE="lighter_live", BULL_MODE=False)
    new = close_extra(TT_VENUE="lighter_live", BULL_MODE=True)

    def _iso(day, hour):
        return _at(day, hour).isoformat()

    rows = []
    # the overlap: two same-pair holds intersecting by 6h, old policy
    rows.append({"bot": LIVE, "pair": "HYPE", "profit_abs": 1.0,
                 "profit_ratio": 0.01, "open_ts": _iso(1, 0),
                 "close_ts": _iso(1, 12), "extra": old})
    rows.append({"bot": LIVE, "pair": "HYPE", "profit_abs": 1.0,
                 "profit_ratio": 0.01, "open_ts": _iso(1, 6),
                 "close_ts": _iso(1, 18), "extra": old})
    for i in range(6):
        rows.append({"bot": LIVE, "pair": f"C{i}", "profit_abs": 2.0,
                     "profit_ratio": 0.01, "open_ts": _iso(10, 6 + i),
                     "close_ts": _iso(11, 6 + i), "extra": new})
    monkeypatch.setattr(store, "fetch_paper_trades", lambda limit=2000: rows)
    monkeypatch.setattr(sys, "argv", ["golive_readiness.py", "--min-closes", "5"])
    g.main()
    out = capsys.readouterr().out
    assert "TWO WRITERS" not in out, (
        "an overlap wholly under the superseded policy vetoed the graded era "
        "— the blocking check is not running over the sample the bars use:\n"
        + out)
    assert "historical overlap(s) predate this era" in out, out
