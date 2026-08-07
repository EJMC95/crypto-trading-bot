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
    """[(call_node, [(test_src, taken_branch), ...])] — the CONDITION CHAIN
    that must hold for this call to run, innermost last.

    [2026-08-07 (lj)] THIS USED TO RETURN A SET OF NAMES, and that made the two
    real-money assertions below VACUOUS. Collecting `{n.id for n in
    ast.walk(p.test)}` cannot tell `if shadow_tag:` from `if not shadow_tag:` —
    `UnaryOp(Not, Name('shadow_tag'))` contains the same name — so inverting
    either guard, which is precisely what would let the LIVE arm size off the
    allocation organ, left the suite GREEN. Measured: both inversions survived.

    That is the `(lh)` class ("an AST assertion that a NAME appears somewhere is
    still a presence check") landing on the guard that keeps a capital lever
    away from real money. The chain is returned with POLARITY — including
    whether the call sits in the `else` branch — so `reachable_when` below can
    ask the only question that matters: can this call run on the live arm?
    """
    tree = ast.parse((ROOT / path).read_text())
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            child._parent = parent
    out = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == func):
            chain, p, prev = [], node, node
            while hasattr(p, "_parent"):
                prev, p = p, p._parent
                if isinstance(p, ast.If):
                    # which limb are we in? `orelse` inverts the test.
                    in_else = any(prev is st or prev in ast.walk(st)
                                  for st in p.orelse)
                    chain.append((ast.unparse(p.test), not in_else))
            out.append((node, list(reversed(chain))))
    return out


def reachable_when(chain, **env):
    """Could a call with this condition chain RUN under `env`?

    Names the caller does not bind are assumed satisfiable (True): the question
    is whether the named condition — `shadow_tag` false, `_is_live` true —
    forbids the call, not whether every unrelated precondition happens to hold.
    A test we cannot evaluate is treated as satisfiable too, which is the
    conservative direction: it can only make a guard look WEAKER, never
    stronger, so this can raise a false alarm but never hide a real one.
    """
    class _Any:
        def __bool__(self):
            return True

        def __getattr__(self, _):
            return _Any()

    for src, want_true in chain:
        ns = dict(env)
        try:
            got = bool(eval(src, {"__builtins__": {}},           # noqa: S307
                            _Env(ns)))
        except Exception:                                        # noqa: BLE001
            got = True
        if got is not want_true:
            return False
    return True


class _Env(dict):
    """Unbound names resolve to a truthy sentinel rather than NameError."""

    def __missing__(self, key):
        if key in ("None", "True", "False"):
            raise KeyError(key)
        return _Truthy()


class _Truthy:
    def __bool__(self):
        return True

    def __getattr__(self, _):
        return _Truthy()

    def __eq__(self, other):
        return True

    def __ne__(self, other):
        return False

    __hash__ = object.__hash__


def test_farmer_reads_allocation_only_behind_its_shadow_gate():
    calls = _guarded_calls("lighter_funding_bot.py")
    assert calls, "the Farmer's shadow arm lost its allocation consumer " \
                  "(registered-but-inert is the failure S1 exists to avoid)"
    for node, chain in calls:
        assert chain, f"line {node.lineno}: allocation_scale is UNGUARDED"
        # THE REAL-MONEY CLAIM: on the live arm (`shadow_tag` falsy) this call
        # must be UNREACHABLE. Asserted by polarity, not by the name appearing
        # in the guard — see `_guarded_calls`.
        assert not reachable_when(chain, shadow_tag=None), (
            f"line {node.lineno}: allocation_scale is reachable on the "
            f"REAL-MONEY Farmer arm (chain: {chain}) — the live arm takes no "
            "capital lever and no allocation ((ia))")
        # ...and it must still RUN on the shadow arm, or the consumer is inert
        assert reachable_when(chain, shadow_tag="shadow"), (
            f"line {node.lineno}: allocation_scale is unreachable even on the "
            f"SHADOW arm (chain: {chain}) — registered-but-inert")


def test_counterweight_reads_allocation_only_when_not_live():
    calls = _guarded_calls("lighter_funding_spread_bot.py")
    assert calls, "Counterweight lost its allocation consumer"
    for node, chain in calls:
        assert chain, f"line {node.lineno}: allocation_scale is UNGUARDED"
        assert not reachable_when(chain, _is_live=True), (
            f"line {node.lineno}: allocation_scale is reachable on the "
            f"REAL-MONEY Counterweight arm (chain: {chain}) — the live arm's "
            "clip is PINNED ((ia))")
        assert reachable_when(chain, _is_live=False), (
            f"line {node.lineno}: allocation_scale is unreachable even on the "
            f"SHADOW arm (chain: {chain}) — registered-but-inert")


def test_carry_consumes_and_both_funding_images_carry_fleet_bus():
    assert _guarded_calls("funding_carry_bot.py"), \
        "carry lost its allocation consumer"
    for df in ("Dockerfile.funding", "Dockerfile.fundinglighter"):
        text = (ROOT / df).read_text()
        assert "fleet_bus.py" in text, (
            f"{df} does not COPY fleet_bus.py — the allocation consumer in "
            f"that image is BORN DARK (guarded import, missing file, silent "
            f"1.0 forever)")
