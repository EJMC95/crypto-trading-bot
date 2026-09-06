"""[2026-09-06 (yd)] A LEVER NAME THE CONSUMER BUILDS ITSELF IS A LEVER THAT
CAN BE UNREACHABLE, SILENTLY — and this closes the CLASS, not the instance.

THE DEFECT. `lighter_family_bot` reconstructed the judge's lever prefix from
the suffixed row id:

    apply_book_levers(b.s, f"xp.{b.bot_id.split('-', 1)[-1]}.")

`bot_id` is `strat.bot + "-lshadow"`, so 👩 mum resolved to `xp.mum-lshadow.`
and 🙏 avo to `xp.avo-maria-lshadow.` — the book's own name contains a hyphen,
which the split cannot know. Neither is in `fleet_tuning.LEVERS`, and
`get_lever` returns the CALLER'S DEFAULT for an unregistered name
(fleet_tuning.py, the `if not spec or spec.get("lane") not in ENACT_LANES`
rung). So every candidate the judge wrote was invisible to the arm meant to
run it, with no error anywhere: the registered-but-inert failure (I18).

MEASURED ON THE LIVE BUS, two consecutive candidates lost to it:
  * `mum-rsi-32`   -> VOIDED-NEVER-APPLIED after 37.7h, the judge's own
    words: "0/4 shadow closes carry a receipt ... the arm is not running
    this experiment";
  * `mum-vel-12-20` -> ran 34h while the arm published
    `vel_band [-999.0, 999.0]`, `vel_in_band 105`, `vel_blocked 0` — the env
    default, untouched, blocking nothing.
That is ~72h of the fleet's ONLY path from a shadow candidate to a
real-money change, spent producing nothing.

WHY THE EXISTING TEST STAYED GREEN, and this is the transferable half:
`test_mum_judge_lane.py` calls `fam.apply_book_levers(s, "xp.mum.")` with the
correct prefix HARD-CODED. It exercises the function and never the call site,
so it can never see a caller passing a different string — a substring test,
not a wiring test. The guard therefore has to assert what the CALL SITE
constructs (by AST), and that every name any arm can construct actually
RESOLVES in the registry.

MUTATIONS THAT MUST TURN THIS RED (verified, see the changelog entry):
  * restoring the f-string at the call site;
  * `xp_prefix_for` returning a rebuilt string instead of the declaration;
  * dropping `xp_prefix` from a JUDGED_PAIRS entry;
  * registering an `xp.*` lever under a token no arm produces;
  * the live host's `_BOOKS` token drifting from the pair declaration.
"""
import ast
import os
import sys
from pathlib import Path

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

import fleet_bus as fb             # noqa: E402
import fleet_tuning as ft          # noqa: E402
import lighter_family_bot as fam   # noqa: E402

pytestmark = pytest.mark.autonomy

FAM_SRC = Path(ROOT, "lighter_family_bot.py").read_text()
LIVE_SRC = Path(ROOT, "lighter_avo_live_bot.py").read_text()


def _calls_to(src, fname):
    """Every ast.Call node in `src` invoking the bare name `fname`."""
    return [n for n in ast.walk(ast.parse(src))
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name) and n.func.id == fname]


def _token(prefix):
    """`xp.mum.` -> `mum`. The book token both hosts must agree on."""
    return prefix.split(".")[1]


def test_every_judged_arm_gets_the_declared_prefix_not_a_rebuilt_one():
    """The derivation is the DECLARATION. Read against the broken arithmetic
    it replaces, so the test carries the evidence of what it prevents."""
    assert fb.JUDGED_PAIRS, "no judged pairs — the guard would be vacuous"
    for pid, spec in fb.JUDGED_PAIRS.items():
        arm = spec["shadow_bot"]
        declared = spec["xp_prefix"]
        assert fam.xp_prefix_for_arm(arm) == declared, (
            f"{pid}: arm {arm} derives "
            f"{fam.xp_prefix_for_arm(arm)!r}, declared {declared!r}")
        # The exact arithmetic that shipped, kept as a NEGATIVE CONTROL so the
        # test carries its own evidence: every name it produces is absent from
        # the registry, which is precisely why get_lever returned the default.
        rebuilt = "xp." + arm.split("-", 1)[-1] + "."
        if rebuilt != declared:
            assert not [n for n in ft.LEVERS if n.startswith(rebuilt)], (
                f"{rebuilt!r} unexpectedly resolves — this control assumes the "
                "rebuilt form names nothing, which is the whole defect")


def test_the_call_site_reads_the_declaration_and_never_builds_the_string():
    """AST, not substring: the SECOND argument of every `apply_book_levers`
    call must be the declared-prefix accessor. An f-string, a concatenation
    or a `.split(...)` there is the defect returning."""
    calls = _calls_to(FAM_SRC, "apply_book_levers")
    assert calls, "no apply_book_levers call site found — guard is vacuous"
    for call in calls:
        assert len(call.args) >= 2, "call site must pass an explicit prefix"
        arg = call.args[1]
        assert not isinstance(arg, (ast.JoinedStr, ast.BinOp)), (
            f"line {arg.lineno}: the prefix is built at the call site "
            "(f-string/concat) — it must come from fleet_bus's declaration")
        assert isinstance(arg, ast.Call) and isinstance(arg.func, ast.Name) \
            and arg.func.id == "xp_prefix_for_arm", (
                f"line {arg.lineno}: prefix must be xp_prefix_for_arm(...)")


def test_the_accessor_reads_judged_pairs_and_does_not_rebuild():
    """`fleet_bus.xp_prefix_for` must LOOK UP `xp_prefix`, never synthesise a
    name. Pinned on the source so a future 'tidy-up' cannot reintroduce the
    string surgery one level down."""
    src = Path(ROOT, "fleet_bus.py").read_text()
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == "xp_prefix_for")
    # NOTE: strip the docstring before inspecting. `ast.dump(fn)` includes it,
    # and this function's docstring QUOTES the broken f-string it replaced —
    # so a naive substring scan over the dump fails on the explanation rather
    # than on the code. (Found by this test failing on its own first run.)
    code = [n for n in fn.body
            if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant))]
    dumped = "".join(ast.dump(n) for n in code)
    assert "'xp_prefix'" in dumped, \
        "the accessor must read the declared xp_prefix field"
    assert not [n for n in ast.walk(ast.Module(body=code, type_ignores=[]))
                if isinstance(n, ast.JoinedStr)], \
        "the accessor must not f-string a prefix together"
    assert not [n for n in ast.walk(ast.Module(body=code, type_ignores=[]))
                if isinstance(n, ast.Attribute) and n.attr == "split"], \
        "the accessor must not rebuild the prefix from a row id"


def test_every_registered_knob_is_actually_asked_for_by_its_own_arm():
    """THE ASSERTION THAT WOULD HAVE FAILED ON THE SHIPPED CODE, and the
    direction that matters: a lever the judge can WRITE must be a name the
    arm will ASK for. (The converse is fine and deliberately not asserted —
    a carrier may ask for a knob nobody has registered yet; the judge cannot
    write it either, so nothing is lost.)"""
    bars = {bar for bar, _a, _c in fam.MUM_LEVER_ATTRS}
    checked = 0
    for pid, spec in fb.JUDGED_PAIRS.items():
        arm = spec["shadow_bot"]
        strat = next((s for s in fam.STRATEGIES
                      if arm.startswith(s.bot + "-")), None)
        # the carrier's OWN gate: apply_book_levers is a no-op without both
        if strat is None or not (hasattr(strat, "RSI_MAX")
                                 and hasattr(strat, "MAX_HOLD_MIN")):
            continue
        asked = {fam.xp_prefix_for_arm(arm) + bar for bar in bars}
        registered = {n for n in ft.LEVERS
                      if n.startswith(spec["xp_prefix"])
                      and n.rsplit(".", 1)[-1] in bars}
        assert registered, f"{pid}: carrier has knobs but no lever is registered"
        missing = registered - asked
        assert not missing, (
            f"{pid}: registered but never asked for: {sorted(missing)} — "
            f"the arm asks for {sorted(asked)}. get_lever returns the default "
            "forever, silently, and every candidate voids.")
        checked += 1
    assert checked, "no carrier with knobs was checked — guard is vacuous"


def test_every_registered_xp_lever_is_reachable_by_some_arm():
    """The mirror direction: a registry entry under a token no arm ever
    produces is a lever the judge can write and nobody can read."""
    tokens = {_token(s["xp_prefix"]) for s in fb.JUDGED_PAIRS.values()}
    xp = [n for n in ft.LEVERS if n.startswith("xp.")]
    assert xp, "no xp.* levers registered — guard is vacuous"
    for name in xp:
        assert _token(name) in tokens, (
            f"{name!r} is registered under a token no judged arm derives "
            f"(arms produce {sorted(tokens)})")


def test_the_live_hosts_token_agrees_with_the_pair_declaration():
    """Both hosts name the same book the same way, or the judge promotes an
    `xp.<a>.` result onto a `live.<b>.` lever. Read from the live host's
    `_BOOKS` by AST so this needs no import (it exits at import on a bad env)."""
    mod = ast.parse(LIVE_SRC)
    books = next((n.value for n in ast.walk(mod)
                  if isinstance(n, ast.Assign)
                  and any(isinstance(t, ast.Name) and t.id == "_BOOKS"
                          for t in n.targets)), None)
    assert isinstance(books, ast.Dict) and books.keys, "_BOOKS not found"
    live_token = {k.value: v.elts[0].value.lower()
                  for k, v in zip(books.keys, books.values)}
    for pid, spec in fb.JUDGED_PAIRS.items():
        book = (spec.get("live_bot") or "").removesuffix("-lighter")
        if book not in live_token:
            continue                      # not a live-capable book (farmer)
        assert live_token[book] == _token(spec["xp_prefix"]), (
            f"{pid}: live host calls it {live_token[book]!r}, the pair "
            f"declares {_token(spec['xp_prefix'])!r} — the judge would "
            "promote across two different books' namespaces")


def test_an_unknown_arm_runs_env_defaults_and_never_invents_a_prefix(monkeypatch):
    """Fail-safe. Junk, a live row, or a dark bus must yield NO lever reads —
    the operator's setting — rather than a name that resolves to nothing."""
    for junk in (None, "", "not-a-book", 123, "freqtrade-mum-lighter"):
        assert fam.xp_prefix_for_arm(junk) == "", f"invented a prefix for {junk!r}"

    asked = []
    monkeypatch.setattr(ft, "get_lever",
                        lambda name, default, **kw: asked.append(name) or default)
    strat = next(s for s in fam.STRATEGIES if s.bot == "freqtrade-mum")
    assert fam.apply_book_levers(strat, "") == {}
    assert asked == [], f"an empty prefix still read levers: {asked}"

    # ...and with the real prefix it asks for exactly the registered names
    fam.apply_book_levers(strat, fam.xp_prefix_for_arm("freqtrade-mum-lshadow"))
    assert asked and all(n in ft.LEVERS for n in asked), asked
