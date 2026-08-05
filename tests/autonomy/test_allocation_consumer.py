"""S1: the allocation organ ACTS on the three funding shadows — and ONLY them.

DECISION (2026-08-05, operator: "Proceed with all of the above" / "Full
permission" on OPERATOR_QUEUE item S1). The allocation organ ranked capital
by claim for four days with ZERO consumers — `fleet_bus.allocation_scale` is
the consumer, wired into 🌾 carry, ⚖️ Counterweight and 💸 the Farmer's
SHADOW arm. These tests pin the four properties that keep S1 the safe move
it was sold as:

  * the accessor is tested against the PUBLISHER'S OWN payload
    (`fleet_allocation.build`), never a hand-written fixture — four dead
    consumers shipped green in one session off fixtures ((hj));
  * REAL MONEY NEVER READS IT — the Farmer's call sits inside its
    `shadow_tag` gate and Counterweight's inside `not _is_live`, checked by
    AST on the real source, not substring ((hm));
  * the kill switch reaches the consumer: `FLEET_ALLOCATION_MODE=advisory`
    returns None from the accessor itself, so every consumer reverts to its
    env default on the next loop without a redeploy;
  * fail-safe: stale organ, unknown book, junk numbers -> None, and the
    consumers treat None as scale-nothing.

Born-dark pin: both funding Dockerfiles must COPY fleet_bus.py — a guarded
import with no COPY is the class this fleet has shipped three times.
"""
import ast
import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

import fleet_allocation
import fleet_bus


def _payload(monkeypatch, books, now=None):
    """Publisher-built payload served through the accessor's own _load."""
    p = fleet_allocation.build(books)
    if now is not None:
        p["updated"] = now.isoformat()
    monkeypatch.setattr(fleet_bus, "_load", lambda key, ct: p
                        if key == "fleet-allocation" else None)
    return p


def _books():
    """One claimed winner, one claimless loser, two flat probes — enough
    cross-section that targets differ from flat. Series carry REAL variance:
    the publisher's own variance floor returns None (undecided) for a
    constant series by design, which this file's first draft learned the
    hard way — the fixture is the publisher's rules, not mine."""
    n = max(20, fleet_allocation.MIN_N)
    return {
        "perps-funding-carry-lshadow": [0.4, 0.6] * (n // 2),   # strong claim
        "perps-funding-spread-lshadow": [-0.4, -0.6] * (n // 2),  # claim 0
        "flat-a-lshadow": [None] * n,                           # no sample
        "flat-b-lshadow": [None] * n,
    }


def test_scale_comes_from_the_publishers_own_targets(monkeypatch):
    p = _payload(monkeypatch, _books())
    base = p["book_usd"]
    win = fleet_bus.allocation_scale("perps-funding-carry-lshadow")
    lose = fleet_bus.allocation_scale("perps-funding-spread-lshadow")
    assert win is not None and lose is not None
    # the winner holds every claim -> all surplus -> clamped at the 4.0 cap
    # or the exact published ratio, whichever is smaller; NON-DEGENERATE.
    exp_win = min(4.0, p["books"]["perps-funding-carry-lshadow"]["target_usd"] / base)
    assert abs(win - exp_win) < 1e-9 and win > 1.0, (win, exp_win)
    # the claimless book sits at the organ's own probe floor
    exp_lose = p["books"]["perps-funding-spread-lshadow"]["target_usd"] / base
    assert abs(lose - max(0.25, exp_lose)) < 1e-9 and lose < 1.0, (lose, exp_lose)


def test_unknown_book_and_stale_payload_scale_nothing(monkeypatch):
    _payload(monkeypatch, _books())
    assert fleet_bus.allocation_scale("no-such-book") is None
    stale = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=2)
    _payload(monkeypatch, _books(), now=stale)
    assert fleet_bus.allocation_scale("perps-funding-carry-lshadow") is None, \
        "a stale organ must scale nothing (I1 — freshness before semantics)"


def test_kill_switch_reaches_the_consumer(monkeypatch):
    _payload(monkeypatch, _books())
    monkeypatch.setenv("FLEET_ALLOCATION_MODE", "advisory")
    assert fleet_bus.allocation_scale("perps-funding-carry-lshadow") is None, \
        "FLEET_ALLOCATION_MODE=advisory must revert every consumer to its " \
        "env default via the accessor — the central-hook pattern"


def test_scale_is_clamped_both_ends(monkeypatch):
    # a lone claimed book among many probes concentrates the whole surplus
    books = dict(_books(), **{f"probe-{i}-lshadow": [None] * 25
                              for i in range(20)})
    _payload(monkeypatch, books)
    s = fleet_bus.allocation_scale("perps-funding-carry-lshadow")
    assert s == 4.0, f"cap must bind at 4.0, got {s}"
    assert fleet_bus.allocation_scale("perps-funding-spread-lshadow") >= 0.25


def _guarded_calls(path, func="allocation_scale"):
    """[(call_node, guard_names_on_the_path)] via a parent-tracked AST walk —
    a page-wide substring scan is not a structural claim ((hm))."""
    tree = ast.parse((ROOT / path).read_text())
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            child._parent = parent
    out = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == func):
            guards = set()
            p = node
            while hasattr(p, "_parent"):
                p = p._parent
                if isinstance(p, ast.If):
                    guards |= {n.id for n in ast.walk(p.test)
                               if isinstance(n, ast.Name)}
            out.append((node, guards))
    return out


def test_farmer_reads_allocation_only_behind_its_shadow_gate():
    calls = _guarded_calls("lighter_funding_bot.py")
    assert calls, "the Farmer's shadow arm lost its allocation consumer " \
                  "(registered-but-inert is the failure S1 exists to avoid)"
    for _, guards in calls:
        assert "shadow_tag" in guards, (
            "an allocation_scale call in the REAL-MONEY Farmer file is not "
            "inside an `if shadow_tag` guard — the live arm takes no capital "
            "lever and no allocation ((ia))")


def test_counterweight_reads_allocation_only_when_not_live():
    calls = _guarded_calls("lighter_funding_spread_bot.py")
    assert calls, "Counterweight lost its allocation consumer"
    for _, guards in calls:
        assert "_is_live" in guards, (
            "Counterweight's allocation_scale call is not guarded by the "
            "`not _is_live` branch — the live arm's clip is PINNED ((ia))")


def test_carry_consumes_and_both_funding_images_carry_fleet_bus():
    assert _guarded_calls("funding_carry_bot.py"), \
        "carry lost its allocation consumer"
    for df in ("Dockerfile.funding", "Dockerfile.fundinglighter"):
        text = (ROOT / df).read_text()
        assert "fleet_bus.py" in text, (
            f"{df} does not COPY fleet_bus.py — the allocation consumer in "
            f"that image is BORN DARK (guarded import, missing file, silent "
            f"1.0 forever)")
