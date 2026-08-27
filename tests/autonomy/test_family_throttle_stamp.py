"""[(uv)] THE ARMS RUN DIFFERENT ENTRY POLICIES AND NEITHER STAMPED IT.

Judge v2's census blocked the georgia pair on `policy_unstamped` naming
`max_entries_per_hour`: the SHADOW throttles entries per clock hour
(`DayTraderGated.MAX_ENTRIES_PER_HOUR = 3`, applied at `throttle_ok`) while the
LIVE host enforces none — and because NEITHER arm stamped the field, it
compared None-to-None, read EQUAL, and slipped through the parity rung in
silence. Measured on the two arms' own ledgers: shadow at-or-over the cap in
2.6% of active hours, live 19.2%, reaching NINE entries in one hour; and the
quantity is one the book's own ledger shows matters (shadow entry_rank 1 =
-0.443%/trade n=24, rank 2 = +0.828% n=9, rank 3 = -7.752% n=3).

These pin the stamp work, NOT the alignment: after this the pair reads
`policy_mismatch` on 3-vs-None, which is the divergence becoming visible and
actionable. Closing it is a separate measured act about real money.
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import fleet_bus                          # noqa: E402
import lighter_family_bot as fam          # noqa: E402


class _Plain:
    """A carrier that is NOT DayTraderGated — it enforces no throttle."""
    style, stoploss, roi = "swingdip", -0.10, {0: 0.20}


def _georgia():
    """A real DayTraderGated INSTANCE — `throttle_cap` asks isinstance, and a
    class is not an instance of itself (the first draft of this test passed the
    class and read None, which would have certified 'no throttle' for the very
    book that has one)."""
    return fam.DayTraderGated(bot="freqtrade-georgia-lshadow", tf="15m",
                              stoploss=-0.05, max_open=5, style="daytrader-15m")


def test_the_stamp_always_carries_the_field_presence_not_truthiness():
    # PRESENCE is the contract: a host with no throttle answers None, and the
    # KEY must still be there. Truthiness would make "no throttle" and "never
    # answered" the same byte-string, which is the hole this closes.
    st = fam.policy_stamp(_Plain(), "lighter_shadow", "list", None)
    assert "max_entries_per_hour" in st, "the field is absent — unstamped again"
    assert st["max_entries_per_hour"] is None
    st3 = fam.policy_stamp(_Plain(), "lighter_shadow", "list", 3)
    assert st3["max_entries_per_hour"] == 3


def test_each_host_answers_for_itself_not_the_strategy():
    # THE MECHANISM: georgia's LIVE arm runs this very DayTraderGated class and
    # enforces NO throttle. A stamp derived from the strategy would certify a
    # throttle the live loop does not apply. So the two hosts must be able to
    # give DIFFERENT answers for the SAME strategy — that is the divergence.
    gated = _georgia()
    shadow = fam.policy_stamp(gated, "lighter_shadow", "list",
                              fam.throttle_cap(gated))
    live = fam.policy_stamp(gated, "lighter_live", "diversified", None)
    assert shadow["max_entries_per_hour"] == gated.MAX_ENTRIES_PER_HOUR
    assert live["max_entries_per_hour"] is None
    assert shadow["max_entries_per_hour"] != live["max_entries_per_hour"], \
        "the arms' throttle divergence is invisible again"


def test_throttle_cap_is_the_one_owner_the_actuator_reads():
    # A second copy would let the stamp certify a throttle the loop does not
    # apply. `throttle_ok` must READ throttle_cap, not re-derive the rule.
    import ast
    src = (ROOT / "lighter_family_bot.py").read_text(encoding="utf-8")
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == "throttle_ok")
    calls = {n.func.id for n in ast.walk(fn)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "throttle_cap" in calls, \
        "throttle_ok stopped reading the one owner — the stamp and the " \
        "actuator can now disagree about whether a book is throttled"
    assert fam.throttle_cap(_Plain()) is None
    assert fam.throttle_cap(_georgia()) == fam.DayTraderGated.MAX_ENTRIES_PER_HOUR


def test_the_new_field_moves_no_era_boundary():
    # THE LOAD-BEARING SAFETY PROPERTY. `stamped_policy_boundary` grades the
    # maximal same-signature SUFFIX of a ledger, so a stamp field that entered
    # the signature would split old rows from new and RESET the era — wiping
    # the very sample this work exists to make judgeable. The signature is
    # built from POLICY_SIG_FIELDS alone; this asserts the field stays out.
    import golive_readiness as gr
    assert "max_entries_per_hour" not in gr.POLICY_SIG_FIELDS, \
        "max_entries_per_hour entered the era signature — adding it there " \
        "weaponises the era and discards every close stamped before it"
    before = gr.stamp_state({"policy": {"venue": "lighter_shadow",
                                        "lenses": ["x"], "sides": ["long"]}})
    after = gr.stamp_state({"policy": {"venue": "lighter_shadow",
                                       "lenses": ["x"], "sides": ["long"],
                                       "max_entries_per_hour": 3}})
    assert before == after, \
        "adding the field changed a row's era signature — the boundary moves"


def test_georgia_pair_still_declares_the_field_and_now_gets_it():
    spec = fleet_bus.JUDGED_PAIRS["georgia"]
    assert "max_entries_per_hour" in spec["policy_fields"]
    # and the pairs that do NOT declare it are unaffected by the new stamp —
    # the parity rung compares only a pair's own policy_fields
    for pid in ("avo", "mum"):
        assert "max_entries_per_hour" not in \
            fleet_bus.JUDGED_PAIRS[pid]["policy_fields"], \
            f"{pid} newly blocks on a field this change added"


def _stamp_call(path, fname=None):
    """The policy_stamp Call node in a host file (AST, not a substring — the
    incident text in these files names the field too)."""
    import ast
    tree = ast.parse(pathlib.Path(path).read_text(encoding="utf-8"))
    return [n for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            and n.func.id == "policy_stamp"]


def test_each_host_actually_passes_its_own_answer_at_the_call_site():
    # WIRING, not just the helper. If a host silently passed None, BOTH arms
    # would stamp None, compare EQUAL, and slip through the parity rung — the
    # precise hole this work closes. Asserting the builder alone would not see
    # it (the "enacted is not applied" class).
    import ast

    shadow = _stamp_call(ROOT / "lighter_family_bot.py")
    assert len(shadow) == 1, f"expected one shadow stamp call, got {len(shadow)}"
    arg = shadow[0].args[3]
    assert isinstance(arg, ast.Call) and isinstance(arg.func, ast.Name) \
        and arg.func.id == "throttle_cap", \
        "the shadow host stopped answering with its OWN cap — if it passes " \
        "None the arms compare equal and the divergence goes silent again"

    live = _stamp_call(ROOT / "lighter_avo_live_bot.py")
    assert len(live) == 1, f"expected one live stamp call, got {len(live)}"
    larg = live[0].args[3]
    assert isinstance(larg, ast.Constant) and larg.value is None, \
        "the live host must answer None — it enforces no hourly throttle; " \
        "passing the strategy's cap would stamp a throttle it does not apply"


def test_the_builder_requires_the_answer_rather_than_defaulting_it():
    # A DEFAULT would let a host forget and still emit a key — and the wrong
    # answer ("no throttle") for a book that has one. Required by signature.
    import inspect
    sig = inspect.signature(fam.policy_stamp)
    par = sig.parameters["max_entries_per_hour"]
    assert par.default is inspect.Parameter.empty, \
        "max_entries_per_hour gained a default — a host can now forget to " \
        "answer and silently stamp the wrong policy"


def test_a_zero_cap_throttles_to_zero_rather_than_unthrottling(monkeypatch):
    """A cap of 0 means NO entries this hour — never "no throttle".

    `if cap is None` and `if not cap` agree on every value the tree currently
    constructs, so the falsy form survives untested — and it inverts exactly
    the case an operator reaches for to STOP a book entering:
    GEORGIA_MAX_ENTRIES_PER_HOUR=0 would silently become UNLIMITED. The gap is
    that no fixture built a 0 cap; this builds one.
    """
    class _Zero(fam.DayTraderGated):
        MAX_ENTRIES_PER_HOUR = 0

    s = _Zero(bot="freqtrade-georgia-lshadow", tf="15m", stoploss=-0.05,
              max_open=5, style="daytrader-15m")
    assert fam.throttle_cap(s) == 0, "a 0 cap must read as 0, never as None"
    assert fam.throttle_cap(s) is not None, \
        "a 0 cap collapsed to None — the book reads as having no throttle"

    book = fam.Book.__new__(fam.Book)
    book.s = s
    book.throttle = {"bucket": -1, "n": 0, "last_rank": None}
    assert book.throttle_ok(0.0) is False, \
        "a 0 cap admitted an entry — `if not cap` unthrottles the very " \
        "setting an operator uses to halt entries"

    # and the stamp reports the 0 rather than erasing it
    assert fam.policy_stamp(s, "lighter_shadow", "list",
                            fam.throttle_cap(s))["max_entries_per_hour"] == 0
