"""[(yj)] TWO WRITES TO ONE STATE KEY IS ONE PAYLOAD, AND THE SECOND WINS.

`bot_pnl_store.save_state` is `INSERT ... ON CONFLICT DO UPDATE SET state =
EXCLUDED.state` — a full REPLACE, not a merge. `market_context.main()` wrote
its per-coin SNAPSHOT to `market-context` and then, four lines later, wrote
`{oi_hist, btc_marks, source}` to the same key. So the snapshot was destroyed
microseconds after it was written, every cycle since the second write landed,
and its one consumer — `lighter_funding_bot._mctx_slice`, which reads `coins`,
`heat_mean_apr` and `btc_vol_1h` — attached six NULL fields to every funding
entry's ledger row instead of the validation dataset it exists to collect.

Nothing gates on it (`audit_bus_contract.RATCHET` says so in as many words),
so what this cost is EVIDENCE rather than trades — which is exactly why it
could run this long with every organ green. The general shape is I1's: a
payload that is present, fresh and wrong looks identical to one that is right,
and only reading the field a consumer actually wants tells them apart.
"""
import ast
import pathlib
from collections import Counter

import pytest

pytestmark = pytest.mark.autonomy

ROOT = pathlib.Path(__file__).resolve().parents[2]


def _static_key(node, consts):
    """The literal state key a `save_state(<key>, ...)` call targets, or None
    when it is computed per-call (a bot id, a loop variable)."""
    if not node.args:
        return None
    a = node.args[0]
    if isinstance(a, ast.Constant) and isinstance(a.value, str):
        return a.value
    if isinstance(a, ast.Name):
        return consts.get(a.id)
    return None


def _module_str_consts(tree):
    out = {}
    for n in tree.body:
        if isinstance(n, ast.Assign) and len(n.targets) == 1 \
                and isinstance(n.targets[0], ast.Name):
            if isinstance(n.value, ast.Constant) and isinstance(n.value.value, str):
                out[n.targets[0].id] = n.value.value
    return out


def _same_block_dupes(tree, consts):
    """Keys written twice from the SAME straight-line block.

    Scoped to one statement list on purpose. A read-modify-write in another
    function (`market_context`'s `coin-vetoes` heartbeat) and two save sites
    in different branches of one helper (`experiment_judge`'s `xp-judge`) are
    both correct, and a naive per-module count calls them defects — which
    would get this guard exempted within a day and then guard nothing. Two
    unconditional writes side by side in one block cannot both survive."""
    bad = {}
    for node in ast.walk(tree):
        for field in ("body", "orelse", "finalbody"):
            block = getattr(node, field, None)
            if not isinstance(block, list):
                continue
            seen = Counter()
            for stmt in block:
                if not isinstance(stmt, ast.Expr):
                    continue
                c = stmt.value
                if isinstance(c, ast.Call) and \
                        getattr(c.func, "attr", None) == "save_state":
                    k = _static_key(c, consts)
                    if k is not None:
                        seen[k] += 1
            for k, n in seen.items():
                if n > 1:
                    bad[k] = max(bad.get(k, 0), n)
    return bad


@pytest.mark.parametrize("mod", ["market_context.py", "lighter_market_scout.py",
                                 "bot_learn.py", "fleet_risk.py",
                                 "evidence_board.py", "experiment_judge.py",
                                 "fleet_immune.py", "fleet_proprioception.py"])
def test_no_block_writes_two_payloads_to_one_state_key(mod):
    """Mutation: point market_context's collector write back at `BOT` => red."""
    path = ROOT / mod
    if not path.exists():
        pytest.skip(f"{mod} not in this tree")
    tree = ast.parse(path.read_text())
    dupes = _same_block_dupes(tree, _module_str_consts(tree))
    assert not dupes, (
        f"{mod} writes these state keys twice from one block: {dupes} — "
        f"save_state REPLACES, so all but the last payload is destroyed")


def test_the_detector_sees_the_defect_it_was_built_for():
    """(po): empty output is not a negative result until the check has been
    seen to produce a positive one. This is that positive control."""
    src = ("K = 'k'\n"
           "def main():\n"
           "    store.save_state('k', snapshot)\n"
           "    store.save_state(K, other)\n")
    tree = ast.parse(src)
    assert _same_block_dupes(tree, _module_str_consts(tree)) == {"k": 2}


def test_market_context_keeps_its_snapshot_and_its_collector_state_apart():
    """The specific fix, named so a future edit cannot quietly re-merge them."""
    import market_context as mc
    assert mc.COLLECTOR_STATE != mc.BOT
    assert mc.COLLECTOR_STATE.startswith(mc.BOT + ":")
    src = (ROOT / "market_context.py").read_text()
    assert 'store.save_state("market-context", snapshot)' in src
    assert "store.save_state(COLLECTOR_STATE," in src


def test_the_collector_state_migrates_off_the_shared_key_once():
    """Splitting the key must not discard 24h of accumulated OI history — the
    read falls back to the legacy key exactly once, on the first boot."""
    src = (ROOT / "market_context.py").read_text()
    i = src.index("_saved = store.load_state(COLLECTOR_STATE)")
    window = src[i:i + 800]
    assert "store.load_state(BOT)" in window, \
        "no fallback: the first boot after the split loses oi_hist/btc_marks"
    assert "oi_hist" in window and "btc_marks" in window
