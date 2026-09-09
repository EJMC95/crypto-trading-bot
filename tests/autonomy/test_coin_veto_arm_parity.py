"""[(zg)] THE COIN-QUALITY VETO RAN ON ONE ARM OF EVERY JUDGED PAIR.

Measured 2026-09-08 on the live payload and both hosts' source:

  * `lighter_avo_live_bot` loaded `coin-vetoes` and refused entries on it, and
    stamped `coin_veto: True` on every close;
  * `lighter_family_bot` — the host that runs EVERY judged pair's CONTROL ARM —
    contained the string `coin_veto` **zero** times;
  * and mum's `policy_fields` was
    `("strategy","venue","stoploss","roi","sides","scan_order")`, so the (sk)
    parity stage — built for exactly this class — could not compare the field
    at all. The one divergence that was already STAMPED was the one nobody
    looked at.

So the twin traded a coin population its live arm refuses, and `control_role:
"load_bearing"` was not true of it. Measured cost of the port on the family
shadow host's own ledgers: **9 refused closes of 533, all loss-making,
-$5.56** (👩 mum 4 x POL at -1.643%/trade, 🔮 georgia 5 x MSTR at -0.966%;
🙏 avo and georgia-v3 zero). Bounded at 4.0% of the worst-affected book's
trades, so nothing is starved (I17/I26) — and the gain is NOT banked: these
coins are vetoed BECAUSE they lost, so "the refused set lost money" is
partly circular (I7). The change is bought as PARITY, at no measured
expectancy cost.

Every test here is mutation-verified — see the file's own docstring table in
the changelog entry.
"""
import ast
import datetime as dt
import pathlib

import pytest

pytestmark = pytest.mark.autonomy

import bot_pnl_store as store            # noqa: E402
import fleet_bus as fb                   # noqa: E402
import lighter_family_bot as fam         # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
FAM_SRC = (ROOT / "lighter_family_bot.py").read_text()
LIVE_SRC = (ROOT / "lighter_avo_live_bot.py").read_text()
NOW = dt.datetime(2026, 9, 8, 6, 0, 0, tzinfo=dt.timezone.utc)


def _fresh(coins, **kw):
    p = {"coins": coins, "updated": "2026-09-08T05:30:00+00:00",
         "ttl_sec": 5400}
    p.update(kw)
    return p


@pytest.fixture
def state(monkeypatch):
    """Swap `store.load_state` — the publisher's own accessor, so the consumer
    is driven against the shape the payload really has ((hj))."""
    box = {}

    def _set(payload):
        box["p"] = payload
        monkeypatch.setattr(store, "load_state", lambda k: box["p"])
    return _set


# ---------------------------------------------------------------- ONE OWNER

def _load_state_veto_calls(src):
    """Every `*.load_state("coin-vetoes")` call site, by AST — a substring scan
    would also match this file's own prose ((po))."""
    out = []
    for node in ast.walk(ast.parse(src)):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        if isinstance(f, ast.Attribute) and f.attr == "load_state":
            for a in node.args:
                if isinstance(a, ast.Constant) and a.value == "coin-vetoes":
                    out.append(node.lineno)
    return out


def test_the_veto_is_read_through_exactly_one_owner():
    """The live host must not carry its own copy of the read: a second copy is
    a second rule, and the arms would drift on TTL, freshness or fail-open."""
    assert _load_state_veto_calls(LIVE_SRC) == [], (
        "lighter_avo_live_bot re-reads `coin-vetoes` itself — call "
        "lighter_family_bot.coin_veto_map so both arms share the read")
    fam_calls = _load_state_veto_calls(FAM_SRC)
    assert len(fam_calls) == 1, (
        f"expected exactly one owner of the read, found {len(fam_calls)}")
    # and it must live INSIDE coin_veto_map, not somewhere else in the module
    fn = next(n for n in ast.walk(ast.parse(FAM_SRC))
              if isinstance(n, ast.FunctionDef) and n.name == "coin_veto_map")
    assert fn.lineno < fam_calls[0] <= (fn.end_lineno or 10**9), (
        "the read is in lighter_family_bot but outside coin_veto_map")


def test_the_live_host_calls_the_shared_owner():
    tree = ast.parse(LIVE_SRC)
    imported = any(
        isinstance(n, ast.ImportFrom) and n.module == "lighter_family_bot"
        and any(a.name == "coin_veto_map" for a in n.names)
        for n in ast.walk(tree))
    assert imported, "the live host must IMPORT coin_veto_map, not redefine it"
    called = any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                 and n.func.id == "coin_veto_map" for n in ast.walk(tree))
    assert called, "the live host imports coin_veto_map and never calls it"


# ------------------------------------------------------------- FAIL-OPEN

@pytest.mark.parametrize("payload,why", [
    (None,                                    "dark bus"),
    ({},                                      "empty payload"),
    ({"coins": {}},                           "no coins"),
    ({"coins": {"POL": "x"}},                 "no timestamp"),
    ({"coins": {"POL": "x"}, "updated": "nope"}, "junk timestamp"),
    (_fresh({"POL": "x"}, updated="2026-09-01T00:00:00+00:00", ttl_sec=3600),
     "stale beyond its own ttl"),
    (_fresh({"POL": "x"}, updated="2026-09-09T00:00:00+00:00"),
     "timestamp in the future"),
    (_fresh("not-a-dict"),                    "coins is not a mapping"),
])
def test_every_doubt_vetoes_nothing(state, payload, why):
    """An organ outage may never narrow a book's universe — the same contract
    `scout_universe` carries. This rule only REMOVES candidates, so failing
    open is the only direction that cannot invent a refusal."""
    state(payload)
    assert fam.coin_veto_map(NOW) == {}, f"must fail OPEN on: {why}"


def test_a_raising_store_vetoes_nothing(monkeypatch):
    def boom(_k):
        raise RuntimeError("db down")
    monkeypatch.setattr(store, "load_state", boom)
    assert fam.coin_veto_map(NOW) == {}


def test_a_fresh_payload_is_actually_returned(state):
    """The mirror of the fail-open tests: a guard that always returns {} would
    pass every one of them and veto nothing, forever (I3)."""
    state(_fresh({"POL": "stop rate 4/8", "SKR": "stop 55/92"}))
    assert fam.coin_veto_map(NOW) == {"POL": "stop rate 4/8",
                                      "SKR": "stop 55/92"}


def test_the_caller_default_ttl_applies_when_the_payload_omits_one(state):
    state({"coins": {"POL": "x"}, "updated": "2026-09-08T05:00:00+00:00"})
    assert fam.coin_veto_map(NOW, 7200.0) == {"POL": "x"}   # 1h old, ttl 2h
    assert fam.coin_veto_map(NOW, 600.0) == {}              # 1h old, ttl 10min


# --------------------------------------------------------- THE SPELLING FOLD

def test_the_lookup_folds_spellings_through_fleet_bus_owner():
    """`sym in mapping` would be a second copy of the namespace rule, and this
    fleet has already paid for the first one. kPOL/1000POL are POL."""
    m = {"POL": "stop rate 4/8"}
    assert fam._fb_coin_evidence_hit(m, "POL") == "stop rate 4/8"
    assert fam._fb_coin_evidence_hit(m, "kPOL") == "stop rate 4/8"
    assert fam._fb_coin_evidence_hit(m, "1000POL") == "stop rate 4/8"
    assert fam._fb_coin_evidence_hit(m, "BTC") is None
    assert fam._fb_coin_evidence_hit({}, "POL") is None
    assert fam._fb_coin_evidence_hit(None, "POL") is None


# ------------------------------------------------------ THE SHADOW'S GATE

def _shadow_veto_branch():
    """The `if <hit>: ... continue` guard in the shadow entry loop, by AST."""
    for node in ast.walk(ast.parse(FAM_SRC)):
        if not isinstance(node, ast.If):
            continue
        inc = [n for n in ast.walk(node)
               if isinstance(n, ast.AugAssign)
               and isinstance(n.target, ast.Subscript)
               and isinstance(n.target.slice, ast.Constant)
               and n.target.slice.value == "coin_veto"]
        if inc:
            return node
    return None


def test_the_shadow_host_refuses_a_vetoed_coin_and_counts_it():
    node = _shadow_veto_branch()
    assert node is not None, (
        "lighter_family_bot has no `b.scan['coin_veto'] += 1` refusal — the "
        "control arm is trading coins its live arm refuses")
    assert isinstance(node.body[-1], ast.Continue), (
        "the veto branch must END the candidate (RESTRICT-only); anything "
        "else lets a vetoed coin fall through to sizing")
    assert node.orelse == [], "the veto must not have an else-branch"


def test_the_shadow_gate_uses_the_shared_lookup_not_a_membership_test():
    src = ast.parse(FAM_SRC)
    assign = [n for n in ast.walk(src)
              if isinstance(n, ast.Assign)
              and any(isinstance(t, ast.Name) and t.id == "_cvhit"
                      for t in n.targets)]
    assert len(assign) == 1, "expected one `_cvhit = ...` in the shadow loop"
    call = assign[0].value
    assert isinstance(call, ast.Call) and isinstance(call.func, ast.Name) \
        and call.func.id == "_fb_coin_evidence_hit", (
        "the shadow gate must fold spellings through the shared owner")
    node = _shadow_veto_branch()
    assert isinstance(node.test, ast.Compare) and \
        isinstance(node.test.left, ast.Name) and node.test.left.id == "_cvhit", (
        "the refusal must branch on the shared lookup's result")


def test_the_shadow_declares_the_bucket_it_increments():
    """A counter incremented but never initialised raises KeyError inside the
    trading loop's own `except` and the refusal vanishes silently."""
    assert '"coin_veto": 0' in FAM_SRC, (
        "b.scan must initialise coin_veto, or the increment is swallowed")


def test_coin_veto_is_a_declared_census_refusal():
    """An undeclared refusal abstains from `binding_gate`, so a book starved
    by the veto would name its runner-up gate — the (vm) lesson."""
    assert "coin_veto" in store.CENSUS_REFUSALS
    assert "coin_veto" not in store.CENSUS_DENOMINATORS


def test_the_port_is_revertible_and_the_revert_is_visible():
    """`FAMILY_COIN_VETO=off` is allowed; hiding it is not — the stamp must
    then report False so the arms diverge and the judge BLOCKS."""
    assert 'FAMILY_COIN_VETO' in FAM_SRC
    on = fam.policy_stamp(_S(), "lighter_shadow", "list", None, True)
    off = fam.policy_stamp(_S(), "lighter_shadow", "list", None, False)
    assert on["coin_veto"] is True and off["coin_veto"] is False, (
        "the stamp must report the setting actually in force")


# ----------------------------------------------------- THE PARITY CONTRACT

class _S:
    style = "oversold-1h"
    stoploss = -0.04
    roi = {0: 0.02}


def test_the_shared_builder_requires_every_host_to_answer():
    """Presence is the contract: a field neither arm stamps compares None to
    None, reads EQUAL, and slips through the parity rung in silence."""
    with pytest.raises(TypeError):
        fam.policy_stamp(_S(), "lighter_shadow", "list", None)   # arity
    assert "coin_veto" in fam.policy_stamp(_S(), "lighter_shadow", "list",
                                           None, True)


def test_the_stamp_is_a_real_bool_never_a_truthy_passthrough():
    st = fam.policy_stamp(_S(), "lighter_shadow", "list", None, "on")
    assert st["coin_veto"] is True, (
        "a raw env string would compare unequal to the live arm's True and "
        "block the judge on a difference that does not exist")


def test_both_hosts_pass_coin_veto_to_the_shared_builder():
    """Driven off the call sites, so a host that stops answering fails here
    rather than at the judge weeks later."""
    for src, who in ((FAM_SRC, "lighter_family_bot"),
                     (LIVE_SRC, "lighter_avo_live_bot")):
        calls = [n for n in ast.walk(ast.parse(src))
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                 and n.func.id == "policy_stamp"]
        assert calls, f"{who} no longer calls policy_stamp"
        for c in calls:
            assert len(c.args) == 5, (
                f"{who} calls policy_stamp with {len(c.args)} args — the "
                f"coin_veto answer is missing")


@pytest.mark.parametrize("pair", ["mum", "avo", "georgia"])
def test_coin_veto_is_policed_on_every_family_pair(pair):
    """THE CLASS-CLOSER. With the field in `policy_fields`, a future arm that
    stops applying the veto reads `policy_mismatch` and BLOCKS, instead of
    the judge computing a biased gap over two coin populations."""
    assert "coin_veto" in fb.JUDGED_PAIRS[pair]["policy_fields"], (
        f"{pair}'s parity check cannot see the coin veto — the exact hole "
        f"that let the divergence run invisibly")


def test_no_family_pair_waives_the_coin_veto():
    """A waiver covers a MEASURED divergence. Nothing has measured this one
    inert, and a waiver added without that measurement re-opens the class."""
    for pair, spec in fb.JUDGED_PAIRS.items():
        assert "coin_veto" not in (spec.get("policy_waived") or {}), (
            f"{pair} waives coin_veto without a measurement")
