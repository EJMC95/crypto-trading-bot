"""A refusal COUNT is uninterpretable — the coins behind it must be named.

Eamon, 2026-09-07, looking at 🙏 avo running on a coin 👩 mum never touched:
*"there's nothing telling mum to jump on that coin."*

There is, and it was telling her the opposite: her own live row published
`uptrend_blocked: 4` that same loop. That is deliberate and measured — mum's
cell requires **NOT (e50 > e200)** because `(qu)` measured the trend filter as
ACTIVELY DESTRUCTIVE in it, so the uptrend supply belongs to 🙏 avo by
construction (all three of her open positions carry `dip_in_uptrend`).

The gap his observation exposes is one level down. **`{uptrend_blocked: 4}` is
byte-identical between four coins that were about to fall and four that ran
140%.** The names existed in the `verdicts` map and were collapsed to an
integer histogram one line later, so the question the observation actually
asks — *what did the coins she refused go on to do?* — could not be answered
from the row's own history at all. That is the `(lv)`/I18 shape (`{open: 0}`
is byte-identical between "quiet" and "structurally impossible") landing on
the fleet's real-money directional row.

These pin the properties that make `refused_coins` answerable rather than
decorative:

  * refusals are NAMED, so the population is reconstructable from history;
  * the bulk verdicts are NOT named — `no_signal` was 95 of mum's 104 names in
    the loop that prompted this, and naming them would bury the 4 that matter
    while inflating every publish;
  * `held`/`opened` stay out, because they already ride their own maps and a
    second copy is a second rule that can drift;
  * truncation is STATED, never inferred — a cap that reaches a reader's
    reasoning is a silent sampling step ((qz));
  * it MOVES NOTHING: no entry, exit, size or gate may read it back.
"""
import ast
import pathlib

import lighter_avo_live_bot as A

ROOT = pathlib.Path(__file__).resolve().parents[2]


def test_the_uptrend_refusal_is_named_not_just_counted():
    """The exact reading that prompted this: 4 coins refused for being in an
    uptrend, in a 104-name universe whose other 95 are `no_signal`."""
    universe = [f"C{i}" for i in range(104)]
    verdicts = {"C0": "held", "C1": "held", "C2": "cooldown",
                "C3": "uptrend_blocked", "C4": "uptrend_blocked",
                "C5": "uptrend_blocked", "C6": "uptrend_blocked",
                "C7": "noncrypto_not_long", "C8": "noncrypto_not_long"}
    verdicts.update({f"C{i}": "no_signal" for i in range(9, 104)})

    got = A.refused_coins(verdicts, universe)

    assert got["uptrend_blocked"]["n"] == 4
    assert got["uptrend_blocked"]["coins"] == ["C3", "C4", "C5", "C6"], (
        "the coins refused for being in an uptrend are not named — the count "
        "alone cannot distinguish four coins about to fall from four that ran")
    assert "no_signal" not in got, (
        "the 95-name bulk verdict is being named: it carries no decision and "
        "would bury the four that do")
    assert "held" not in got and "opened" not in got, (
        "held/opened already ride their own maps — a second copy can drift")


def test_a_verdict_nothing_hit_is_absent_not_empty():
    """I8: an empty entry on the row reads as 'refused, names unknown'."""
    got = A.refused_coins({"A": "no_signal"}, ["A"])
    assert got == {}, f"expected an empty result, got {got}"
    for why in A.NAMED_REFUSALS:
        assert why not in got


def test_truncation_is_stated_and_the_true_count_survives_it():
    """(qz): a cap that reaches a reader's reasoning is a silent sampling
    step. The count must be the REAL one, and the cut must be declared."""
    universe = [f"K{i}" for i in range(40)]
    verdicts = {f"K{i}": "coin_veto" for i in range(40)}
    got = A.refused_coins(verdicts, universe, cap=12)
    assert got["coin_veto"]["n"] == 40, (
        "the published count was capped along with the list — the reader "
        "cannot tell 40 refusals from 12")
    assert len(got["coin_veto"]["coins"]) == 12
    assert got["coin_veto"]["truncated"] is True

    small = A.refused_coins({"K0": "coin_veto"}, ["K0"], cap=12)
    assert "truncated" not in small["coin_veto"], (
        "an untruncated list flags itself as truncated — a reader who learns "
        "the flag is always present learns to ignore it")


def test_a_coin_outside_the_universe_is_not_reported():
    """`verdicts` is durable across loops ((st)); a coin that has LEFT the
    universe must not keep appearing as a live refusal."""
    got = A.refused_coins({"GONE": "uptrend_blocked", "HERE": "uptrend_blocked"},
                          ["HERE"])
    assert got["uptrend_blocked"]["coins"] == ["HERE"]
    assert got["uptrend_blocked"]["n"] == 1


def test_the_census_publishes_it_and_omits_it_when_clean():
    """Driven through the real `scan_census`, not asserted about it."""
    common = dict(rsi_readings={}, rsi_bar=36.0, universe=["A", "B"],
                  held={}, ungraded=[], entries_shut=None, last_open_ts=None,
                  last_close_ts=None, t_now=0.0)
    hit = A.scan_census(verdicts={"A": "uptrend_blocked", "B": "no_signal"},
                        **common)
    assert hit["refused_coins"]["uptrend_blocked"]["coins"] == ["A"]

    clean = A.scan_census(verdicts={"A": "no_signal", "B": "no_signal"},
                          **common)
    assert "refused_coins" not in clean, (
        "the field is published empty when nothing was refused — an empty "
        "dict on the row reads as 'refused, names unknown' (I8)")


def test_nothing_reads_the_refusal_names_back():
    """MOVES NOTHING, by AST over the whole module rather than a substring
    scan ((po)): `refused_coins` may be CALLED, and its result may only be
    stored into the census dict — never consumed by a gate, a size or a stop.
    """
    src = (ROOT / "lighter_avo_live_bot.py").read_text()
    tree = ast.parse(src)
    # Load context only: `out["refused_coins"] = ...` is the PUBLISH site and
    # is a Store. Banning that would ban the field itself; what must not exist
    # is a READ of it back out.
    reads = [n for n in ast.walk(tree)
             if isinstance(n, ast.Subscript)
             and isinstance(n.slice, ast.Constant)
             and n.slice.value == "refused_coins"
             and isinstance(n.ctx, ast.Load)]
    assert not reads, (
        "something reads `refused_coins` back out of the payload — it is "
        "REPORTED, and a consumer would make a telemetry field into a rule "
        "nobody measured")
    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Name)
             and n.func.id == "refused_coins"]
    assert len(calls) == 1, (
        f"expected exactly one call site (the census), found {len(calls)}")
