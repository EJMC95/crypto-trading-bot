#!/usr/bin/env python3
"""[2026-08-27] THE WIRE — 🧬 the incubator's champion reaches a replay gate.

WHY THIS FILE EXISTS. The incubator computed a valid, clamped, in-cage lever
dict every cycle (`genotype_to_levers`) and handed it to NOBODY: measured by
AST over 423 .py files, its only two call sites were inside the incubator's own
`_selftest`. The organ bred, swept ~1500 genotypes, ranked them, gated them and
published a card — and no bot could ever read the answer.

WHAT THESE TESTS PIN, in the order the safety depends on it:

  1. THE CHANNEL. `run_once` calls `fleet_proposals.propose`, and this module
     calls `fleet_tuning.write_levers` NOWHERE. A proposal enacts nothing — the
     scout tuner replay-gates it against the recorded tape before any lever
     moves. Writing the lever directly would hand an UNREPLAYED genotype to a
     running book. Asserted on the AST, never on a substring: this file's own
     prose contains both names.
  2. THE POSITIVE CONTROL, which every negative below is vacuous without: a
     STABLE champion driven through the REAL `run_once` against the REAL
     `fleet_proposals.propose` lands proposals with the right author and lane.
  3. THE LOAD-BEARING NEGATIVE — today's live state. The champion is
     `tentative`, streak 0, weak half. It must propose NOTHING.
  4. THE FRONTIER REFUSAL, driven on the genotype the live payload published
     on 26-Aug. `genotype_to_levers` returns SEVEN levers for it and silently
     CLAMPS FOUR — a configuration that was never scored. That is the (sk)
     BRK_RANGE lesson, and it is why enactability is re-checked at the wire.
  5. FAIL-SAFE DIRECTION. A dark or raising channel proposes nothing and never
     raises; an underivable direction refuses rather than guessing.
  6. NO ROUTE TO REAL MONEY, from this author, ever.
"""
import ast
import copy
import importlib
import os
import pathlib
import sys
import types

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("TT_VENUE", "lighter_shadow")

import fleet_proposals as fprop            # noqa: E402
import fleet_tuning as tuning              # noqa: E402
import lighter_ticket_taker as tt          # noqa: E402
import strategy_incubator as inc           # noqa: E402

SRC = pathlib.Path(inc.__file__).read_text(encoding="utf-8")
TREE = ast.parse(SRC)

# The genotypes the LIVE payload published on 2026-08-26T23:44:30Z. Kept as
# literals on purpose: these are the two shapes the wire has to tell apart, and
# a fixture invented by whoever wrote the consumer is exactly the trap
# `test_payload_contracts` exists to close.
LIVE_CHAMPION_GT = {"MOMO_CHG": 4.0, "BRK_RANGE": 0.90, "DIP_RANGE": 0.15,
                    "STOP_LOSS": -0.03, "DIV_GAP_PP": 87.5,
                    "MAX_HOLD_H": 48.0, "TAKE_PROFIT": 0.04}
LIVE_FRONTIER_GT = {"MOMO_CHG": 5.0, "BRK_RANGE": 0.97, "DIP_RANGE": 0.08,
                    "STOP_LOSS": -0.015, "DIV_GAP_PP": 100.0,
                    "MAX_HOLD_H": 24.0, "TAKE_PROFIT": 0.04}


def taker_defaults():
    return {g: getattr(tt, g) for g in inc.TAKER_GENES}


def champ(genotype, **over):
    """A champion dict shaped exactly as `run_once` builds one."""
    out = {"genotype": dict(genotype), "net": 100.0, "h1": 50.0, "h2": 50.0,
           "confidence": "stable", "streak": inc.PERSIST_CYCLES, "stable": True,
           "closes": 66, "lcb": 18.14, "vs_default": 86.0}
    out.update(over)
    return out


# ---------------------------------------------------------------------------
# 1. THE CHANNEL — asserted on the AST
# ---------------------------------------------------------------------------

def _calls_in(node):
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Attribute):
                mod = f.value.id if isinstance(f.value, ast.Name) else None
                yield mod, f.attr, n
            elif isinstance(f, ast.Name):
                yield None, f.id, n


def _func(name):
    for n in ast.walk(TREE):
        if isinstance(n, ast.FunctionDef) and n.name == name:
            return n
    raise AssertionError(f"{name}() not found in strategy_incubator.py")


def test_run_once_proposes_through_the_proposal_channel():
    """run_once must CALL fleet_proposals.propose — the wire itself."""
    hits = [(m, a) for m, a, _ in _calls_in(_func("run_once"))
            if a == "propose"]
    assert hits, ("run_once() does not call propose() — the champion is being "
                  "computed and handed to nobody, which is the whole defect "
                  "this wire closes")
    assert any(m == "fprop" for m, _ in hits), (
        f"propose() is called on the wrong module in run_once: {hits}. The "
        f"channel is fleet_proposals (imported as `fprop`), because a "
        f"proposal is replay-gated at the tuner and enacts nothing.")


def test_the_incubator_never_writes_a_lever_itself():
    """No write_levers / release_levers ANYWHERE in the module.

    The proposal channel is the safety: the scout tuner gates every entry
    through its own replay before a lever moves. A direct write would hand an
    unreplayed genotype straight to a running book."""
    banned = {"write_levers", "release_levers"}
    found = sorted({(m, a) for m, a, _ in _calls_in(TREE) if a in banned})
    assert not found, (
        f"strategy_incubator calls a lever WRITER: {found}. This organ "
        f"proposes; it does not enact. Route it through fleet_proposals.")


def test_the_ast_check_is_not_a_substring_check():
    """Positive control for the guard above: the banned names appear as TEXT in
    this very module's docstring and in the incubator's own comments, so a
    substring scan would fire on prose and a real call would be
    indistinguishable from a mention."""
    assert "write_levers" in SRC, (
        "expected the incubator's own commentary to mention write_levers — if "
        "it no longer does, this control has stopped controlling anything")
    banned_calls = [a for _m, a, _n in _calls_in(TREE) if a == "write_levers"]
    assert not banned_calls, "mention is not a call — and there must be none"


# ---------------------------------------------------------------------------
# 2. THE POSITIVE CONTROL — a STABLE champion actually lands a proposal
# ---------------------------------------------------------------------------

class _Store:
    """A stub bot_pnl_store: records every save, answers reads from `state`."""

    def __init__(self, state=None):
        self.state = dict(state or {})
        self.saved = {}
        self.history = []

    def load_state(self, key):
        return copy.deepcopy(self.state.get(key))

    def load_state_checked(self, key):
        return True, copy.deepcopy(self.state.get(key) or {})

    def save_state(self, key, payload):
        self.saved[key] = copy.deepcopy(payload)
        self.state[key] = copy.deepcopy(payload)
        return True

    def save_history(self, key, row):
        self.history.append((key, row))
        return True

    def fetch_paper_trades(self, **_kw):
        return []


def _drive_run_once(monkeypatch, *, genotype, streak_before,
                    prop_store=None, fprop_module="real"):
    """Run the REAL run_once with the heavy parts stubbed and nothing else.

    Stubbed: the tape fetch, the per-genotype replay (`rank`), and the daily
    up-resolver (network). NOT stubbed — and this is the point — the champion
    gate, the enactability check, the direction derivation, the proposal
    builder, and (unless the caller says otherwise) `fleet_proposals.propose`
    itself, so the registry clamp and the author-lane filter really run.
    """
    from datetime import datetime, timedelta, timezone
    t0 = datetime(2026, 8, 20, tzinfo=timezone.utc)
    tape = [(t0 + timedelta(hours=2 * i), {}) for i in range(80)]   # 158h

    default_gt = {g: getattr(tt, g) for g in inc.TAKER_GENES}
    scored = [
        {"genotype": dict(genotype), "net": 100.0, "h1": 50.0, "h2": 50.0,
         "closes": 66, "lcb": 18.14, "both_halves_pos": True},
        {"genotype": dict(default_gt), "net": 0.0, "h1": 0.0, "h2": 0.0,
         "closes": 50, "lcb": -1.0, "both_halves_pos": False},
    ]

    store = _Store({inc.KEY: {"champion": {"genotype": dict(genotype),
                                           "streak": streak_before},
                              "elite": [], "prospects": [], "proposed": []},
                    inc.QUEUE_KEY: {}})
    monkeypatch.setattr(inc, "store", store)
    monkeypatch.setattr(inc, "EXPLORE_N", 4)          # keep the sweep cheap
    monkeypatch.setattr(inc.rp, "load_tape", lambda source=None: (tape, "stub"))
    monkeypatch.setattr(inc, "build_up_resolver", lambda *_a, **_k: None)
    monkeypatch.setattr(inc, "rank", lambda *_a, **_k: copy.deepcopy(scored))

    if fprop_module != "real":
        monkeypatch.setattr(inc, "fprop", fprop_module)
    else:
        monkeypatch.setattr(fprop, "store", prop_store or _Store())
        monkeypatch.setattr(fprop, "_cache", {"ts": 0.0, "payload": None})
    return inc.run_once(), store


def test_a_stable_champion_lands_a_proposal_with_the_right_author_and_lane(
        monkeypatch):
    """THE POSITIVE CONTROL. Without it every negative below is vacuous."""
    pstore = _Store()
    payload, _store = _drive_run_once(
        monkeypatch, genotype=LIVE_CHAMPION_GT,
        streak_before=inc.PERSIST_CYCLES - 1, prop_store=pstore)

    prop = payload["proposal"]
    assert prop["refused"] is None, prop["refused"]
    assert prop["sent"] is True, prop
    assert prop["levers"], "a stable champion proposed nothing"

    written = pstore.saved.get(fprop.KEY)
    assert written, ("nothing reached bot_state 'tuning-proposals' — the "
                     "channel did not actually carry the proposal")
    entries = written["proposals"]
    mine = {k: v for k, v in entries.items()
            if v.get("set_by") == inc.PROPOSE_AUTHOR}
    assert mine, f"no entry authored by {inc.PROPOSE_AUTHOR}: {entries}"
    for key, e in mine.items():
        assert key == f"{inc.PROPOSE_AUTHOR}:{e['lever']}", key
        assert e["direction"] in ("restrict", "expand"), e
        lane = (tuning.LEVERS.get(e["lever"]) or {}).get("lane")
        assert lane == "lighter-taker", (
            f"{e['lever']} is on lane {lane!r} — the incubator proposes on the "
            f"$1k SHADOW taker lane and nowhere else")
        # the value must be the allele that was SCORED, not a clamped cousin
        assert tuning.clamp(e["lever"], e["value"]) == e["value"], e

    # and the channel's own reader agrees the entries are valid
    fresh = fprop.fresh_proposals()
    assert any(p["set_by"] == inc.PROPOSE_AUTHOR for p in fresh), fresh


def test_the_wire_state_is_published_even_when_it_proposes_nothing(monkeypatch):
    """`{levers: {}}` must never be byte-identical between 'nothing qualified'
    and 'the wire is broken' — the (lv) rule, applied to this channel."""
    payload, _ = _drive_run_once(monkeypatch, genotype=LIVE_CHAMPION_GT,
                                 streak_before=0)
    prop = payload["proposal"]
    assert set(prop) >= {"author", "levers", "refused", "sent",
                         "no_consumer", "current"}, prop
    assert prop["levers"] == {}
    assert prop["sent"] is False
    assert prop["refused"], "an empty channel with no stated reason"


# ---------------------------------------------------------------------------
# 3. THE LOAD-BEARING NEGATIVE — today's live state proposes NOTHING
# ---------------------------------------------------------------------------

def test_a_tentative_champion_proposes_nothing(monkeypatch):
    """Live state, 26-Aug: net +$52.47, h2 −$9.09, streak 0, `tentative`.

    One cycle's fittest is a max over ~1500 genotypes — the winner's curse
    `rank()` exists to avoid. Only PERSIST_CYCLES of the SAME genotype earns
    the wire."""
    payload, _ = _drive_run_once(monkeypatch, genotype=LIVE_CHAMPION_GT,
                                 streak_before=0)
    assert payload["proposal"]["levers"] == {}
    assert payload["proposal"]["sent"] is False
    assert "STABLE" in payload["proposal"]["refused"]


@pytest.mark.parametrize("streak", list(range(0, inc.PERSIST_CYCLES)))
def test_every_sub_persistence_streak_is_refused(streak):
    """The bar is `streak >= PERSIST_CYCLES`, not `is_champion`."""
    view = inc.champion_proposal(
        champ(LIVE_CHAMPION_GT, stable=False, streak=streak),
        taker_defaults(), inc._tighter_map())
    assert view["levers"] == {}, f"streak {streak} must not propose"
    assert "STABLE" in view["refused"]


def test_a_champion_flagged_stable_at_the_bar_does_propose():
    """The other side of the same bar — otherwise the test above passes by
    refusing everything."""
    view = inc.champion_proposal(champ(LIVE_CHAMPION_GT), taker_defaults(),
                                 inc._tighter_map())
    assert view["refused"] is None and view["levers"], view


# ---------------------------------------------------------------------------
# 4. THE FRONTIER REFUSAL — an out-of-cage genotype never proposes
# ---------------------------------------------------------------------------

def test_the_live_frontier_genotype_would_clamp_to_something_never_scored():
    """The measurement the refusal rests on, driven rather than asserted.

    If `genotype_to_levers` ever stops clamping this genotype, the refusal
    below is no longer testing anything and this control says so."""
    levers = inc.genotype_to_levers(LIVE_FRONTIER_GT, inc.TAKER_GENES)
    clamped = {g: (v, levers.get(inc.TAKER_GENES[g][0]))
               for g, v in LIVE_FRONTIER_GT.items()
               if levers.get(inc.TAKER_GENES[g][0]) != v}
    assert clamped, ("the live frontier genotype no longer clamps — re-check "
                     "the cage before trusting the refusal test below")
    assert len(levers) == len(LIVE_FRONTIER_GT), (
        "genotype_to_levers dropped a gene rather than clamping it; the "
        "refusal must still hold, but the hazard has changed shape")


def test_a_frontier_genotype_is_refused_even_when_stable():
    view = inc.champion_proposal(champ(LIVE_FRONTIER_GT), taker_defaults(),
                                 inc._tighter_map())
    assert view["levers"] == {}, (
        "the FRONTIER was proposed — it clamps to a configuration that was "
        "never scored ((sk) BRK_RANGE)")
    assert "ENACTABLE" in view["refused"], view["refused"]


def test_a_single_out_of_cage_allele_refuses_the_whole_genotype():
    """Not 'drop that lever and propose the rest': a partial genotype was not
    scored either."""
    gt = dict(LIVE_CHAMPION_GT, DIV_GAP_PP=100.0)      # cage hi is 87.5
    view = inc.champion_proposal(champ(gt), taker_defaults(),
                                 inc._tighter_map())
    assert view["levers"] == {} and view["refused"], view


def test_the_clamp_is_re_derived_at_the_wire_not_inherited():
    """Belt and braces. `is_enactable` falls back to RESEARCH_GENES for a gene
    the caller's map omits, so it can PASS a genotype `genotype_to_levers`
    then drops. The per-gene clamp loop is what catches that, and it must
    refuse the whole thing."""
    genes = {g: spec for g, spec in inc.TAKER_GENES.items() if g != "MOMO_CHG"}
    gt = dict(LIVE_CHAMPION_GT)
    assert inc.is_enactable(gt, genes) is True, (
        "precondition of this test: is_enactable passes via the RESEARCH_GENES "
        "fallback even though the caller's gene map omits MOMO_CHG")
    view = inc.champion_proposal(champ(gt), taker_defaults(),
                                 inc._tighter_map(), genes=genes)
    assert view["levers"] == {}, "a gene with no lever mapping must refuse"
    assert "clamp mismatch" in view["refused"], view["refused"]


def test_the_wire_derives_its_levers_through_the_one_owner():
    """`champion_proposal` must build `levers` with `genotype_to_levers`.

    A mutation replacing that call with an inline `{genes[g][0]: v ...}` dict
    SURVIVED the round, and it is worth naming precisely because it changes no
    behaviour today: `is_enactable` refuses the out-of-cage case before this
    line, so the inline version is observationally identical. What it deletes
    is the INDEPENDENCE — the check stops re-deriving the clamp through the
    same function a real enactment would use and starts asserting the genotype
    against itself, a tautology. The whole reason precondition 2 is re-checked
    at the wire is that `genotype_to_levers` and `is_enactable` can DISAGREE
    ((sk) BRK_RANGE); a copy of the rule is a second rule ((hj)), and a second
    rule that always agrees with its input cannot catch the disagreement."""
    hits = [(m, a) for m, a, _ in _calls_in(_func("champion_proposal"))
            if a == "genotype_to_levers"]
    assert hits, ("champion_proposal() does not call genotype_to_levers() — "
                  "its clamp check is no longer an independent derivation")
    assert all(m is None for m, _ in hits), f"unexpected owner: {hits}"


def test_two_genes_on_one_lever_reach_the_clamp_mismatch_arm():
    """THE OTHER HALF of the guard above, and it was DECLARED untested.

    The test above reaches the `lever is None` branch only, so a mutation
    deleting `or levers.get(lever) != v` SURVIVED the round — the arm was
    described as belt-and-braces against "a future gene map". It is not
    hypothetical and it is reachable today: `is_enactable` clamps each gene
    against its OWN lever and passes, while `genotype_to_levers` builds a dict
    KEYED BY LEVER, so two genes sharing one lever silently collapse to the
    last one written. The surviving value is an allele the OTHER gene never
    scored, which is precisely what this wire must never propose.
    """
    spec = inc.TAKER_GENES["MOMO_CHG"]
    genes = dict(inc.TAKER_GENES, ALIAS=spec)          # two genes, one lever
    gt = {"MOMO_CHG": 4.0, "ALIAS": 5.0}
    assert tuning.clamp(spec[0], 4.0) == 4.0 and tuning.clamp(spec[0], 5.0) == 5.0, (
        "precondition: BOTH alleles are in-cage, so nothing but the collision "
        "can refuse this genotype")
    assert inc.is_enactable(gt, genes) is True, (
        "precondition: the enactability gate PASSES this genotype — the clamp "
        "loop is the only thing standing between it and the channel")
    collapsed = inc.genotype_to_levers(gt, genes)
    assert collapsed == {spec[0]: 5.0}, (
        f"precondition: the two genes collapse to one lever; got {collapsed}")

    view = inc.champion_proposal(champ(gt), taker_defaults(),
                                 inc._tighter_map(), genes=genes)
    assert view["levers"] == {}, (
        "a genotype that collapses to a value one of its genes never carried "
        "was proposed — the whole genotype must be refused")
    assert "clamp mismatch" in view["refused"], view["refused"]


def test_an_empty_genotype_is_no_champion_not_a_silent_match():
    """`{}` must take the `no champion` exit, not fall through to the loop.

    With `or not gt` deleted an empty genotype still refuses — but through the
    "matches the taker's running configuration" branch, which is a different
    claim about a different state. A refusal reason is the record (I23), and
    on this payload it is the ONLY thing that tells a reader why the channel
    is empty."""
    view = inc.champion_proposal(champ({}), taker_defaults(),
                                 inc._tighter_map())
    assert view["levers"] == {}
    assert "no champion" in view["refused"], view["refused"]


# ---------------------------------------------------------------------------
# 5. FAIL-SAFE DIRECTION — dark, raising, or underivable => no proposal
# ---------------------------------------------------------------------------

def test_a_dark_proposal_channel_degrades_to_no_proposal(monkeypatch):
    """The DECLARED dark-channel exit — asserted specifically, because the
    generic one says "dark" too.

    A mutation deleting `if fprop is None:` SURVIVED the first round: the call
    then raises `AttributeError` on None, the bare `except` catches it, and the
    fallback reason ("propose() did not land — dark DB, ...") also contains the
    word "dark". So the original substring assertion could not tell a designed
    refusal from a crash it happened to recover from — and the recovery is only
    as good as an `except Exception` a later narrowing could take away (which
    is exactly what `test_a_raising_proposal_channel...` mutates). Two signals
    separate them: the unimportable wording, and the ABSENCE of `error`, which
    only the crash path sets."""
    payload, _ = _drive_run_once(monkeypatch, genotype=LIVE_CHAMPION_GT,
                                 streak_before=inc.PERSIST_CYCLES - 1,
                                 fprop_module=None)
    prop = payload["proposal"]
    assert prop["levers"], "the champion still qualified — only the channel is dark"
    assert prop["sent"] is False
    assert "dark" in prop["refused"].lower(), prop["refused"]
    assert "unimportable" in prop["refused"], (
        f"the dark-channel branch did not run; this reason is the generic "
        f"did-not-land one: {prop['refused']!r}")
    assert "error" not in prop, (
        f"an exception was caught and recovered from — that is the crash path, "
        f"not the declared `fprop is None` exit: {prop.get('error')!r}")


def test_a_raising_proposal_channel_never_takes_the_cycle_down(monkeypatch):
    boom = types.SimpleNamespace(
        propose=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")),
        KEY=fprop.KEY)
    payload, store = _drive_run_once(
        monkeypatch, genotype=LIVE_CHAMPION_GT,
        streak_before=inc.PERSIST_CYCLES - 1, fprop_module=boom)
    assert payload is not None, "a raising channel killed the whole cycle"
    assert payload["proposal"]["sent"] is False
    assert "boom" in payload["proposal"].get("error", ""), payload["proposal"]
    assert store.saved.get(inc.KEY), "the payload was not published"


def test_a_channel_that_does_not_land_is_never_reported_as_sent(monkeypatch):
    """`fleet_proposals.propose` returns None when the durable write fails —
    the landed-signal contract. Reporting that as sent would be I4's silent
    write failure at this seam."""
    quiet = types.SimpleNamespace(propose=lambda *a, **k: None, KEY=fprop.KEY)
    payload, _ = _drive_run_once(monkeypatch, genotype=LIVE_CHAMPION_GT,
                                 streak_before=inc.PERSIST_CYCLES - 1,
                                 fprop_module=quiet)
    assert payload["proposal"]["sent"] is False
    assert "did not land" in payload["proposal"]["refused"]


def test_an_underivable_direction_refuses_rather_than_guessing():
    for dark in (None, {}):
        view = inc.champion_proposal(champ(LIVE_CHAMPION_GT),
                                     taker_defaults(), dark)
        assert view["levers"] == {}, "a guessed direction is not a direction"
        assert "direction" in view["refused"], view["refused"]


def test_the_direction_map_is_none_never_empty_when_unreadable(monkeypatch):
    """None and {} are both falsy to the caller — but only None can be told
    apart from 'the tuner consumes no levers'. Keep the honest one."""
    monkeypatch.setitem(sys.modules, "lighter_scout_tuner", None)
    importlib.invalidate_caches()
    assert inc._tighter_map() is None


@pytest.mark.parametrize("owner_map, why", [
    ({}, "the owner consumes nothing"),
    ({"taker.momo_chg": ("MOMO_CHG", "sideways")}, "no usable direction"),
])
def test_an_empty_owner_map_also_degrades_to_none(monkeypatch, owner_map, why):
    """The `or None` on the return, which the test above cannot reach.

    That one kills the IMPORT failure; a mutation to `return m` survived it,
    because an owner map that is present but yields nothing usable takes a
    different path to the same falsy value. The docstring's claim is `None,
    NEVER {}` — an empty dict says "the tuner reads no levers", a fact, while
    None says "I could not derive this", a refusal. The caller treats them
    alike TODAY; the moment one of them is reported or logged they stop being
    interchangeable, and the honest one has to already be there."""
    tuner = importlib.import_module("lighter_scout_tuner")
    monkeypatch.setattr(tuner, "PROPOSAL_TAKER", owner_map)
    assert inc._tighter_map() is None, why


def test_run_once_derives_its_directions_from_the_owner_every_cycle():
    """`run_once` must CALL `_tighter_map()`, not carry a map of its own.

    The owner test above drives `_tighter_map` directly, so replacing the CALL
    SITE in run_once with a hard-coded dict SURVIVED the round — the drift class
    the helper exists to prevent, reintroduced one frame up and just as silent
    (the tuner disqualifies a mismatched direction, so the channel keeps looking
    alive while enacting nothing, forever)."""
    hits = [(m, a) for m, a, _ in _calls_in(_func("run_once"))
            if a == "_tighter_map"]
    assert hits, ("run_once() does not call _tighter_map() — the tighter "
                  "directions are coming from somewhere else, which is a "
                  "second copy of lighter_scout_tuner.PROPOSAL_TAKER")
    assert all(m is None for m, _ in hits), f"unexpected owner: {hits}"


def test_a_dark_direction_map_reaches_the_published_wire_state(monkeypatch):
    """And the call's RESULT must be what the wire uses — an AST hit alone
    cannot tell a consumed value from a discarded one."""
    monkeypatch.setattr(inc, "_tighter_map", lambda: None)
    payload, _ = _drive_run_once(monkeypatch, genotype=LIVE_CHAMPION_GT,
                                 streak_before=inc.PERSIST_CYCLES - 1)
    prop = payload["proposal"]
    assert prop["levers"] == {}, (
        "the champion is STABLE and ENACTABLE, so only the direction map "
        "stands between it and the channel — its refusal must bind here")
    assert prop["sent"] is False
    assert "direction" in prop["refused"], prop["refused"]


def test_the_direction_map_is_read_from_its_owner_not_copied(monkeypatch):
    """A second copy of this map would be a second rule, and wrong is SILENT:
    the tuner disqualifies a mismatched direction, so a drifted copy leaves
    the channel looking alive and enacting nothing forever."""
    tuner = importlib.import_module("lighter_scout_tuner")
    monkeypatch.setattr(tuner, "PROPOSAL_TAKER",
                        {"taker.momo_chg": ("MOMO_CHG", "down")})
    assert inc._tighter_map() == {"taker.momo_chg": "down"}, (
        "the incubator is not reading lighter_scout_tuner.PROPOSAL_TAKER — it "
        "is carrying its own copy of the tighter-direction map")


def test_the_declared_direction_survives_the_tuners_own_re_derivation(
        monkeypatch):
    """THE CROSS-CHECK, driven through EVERY hop of the real road.

    build -> `fleet_proposals.propose` -> the `tuning-proposals` payload ->
    the tuner's own `proposals_for(set(PROPOSAL_TAKER))` -> `consume_proposals`,
    which re-derives the direction and DISQUALIFIES a mismatch before any
    replay runs. The replay is stubbed to refuse everything, so this asserts
    the one thing it is about: no entry is thrown out because the incubator
    declared a direction the consumer derives differently."""
    tuner = importlib.import_module("lighter_scout_tuner")
    view = inc.champion_proposal(champ(LIVE_CHAMPION_GT), taker_defaults(),
                                 inc._tighter_map())
    assert view["levers"], "nothing to cross-check"

    monkeypatch.setattr(fprop, "store", _Store())
    monkeypatch.setattr(fprop, "_cache", {"ts": 0.0, "payload": None})
    assert fprop.propose(view["levers"], set_by=inc.PROPOSE_AUTHOR) is not None
    proposals = fprop.proposals_for(set(tuner.PROPOSAL_TAKER))
    assert proposals, (
        "the tuner's own fetch saw NOTHING — every lever the incubator "
        "proposed is outside the set the tuner reads, so the wire ends in a "
        "key nobody opens")

    saved = (tuner.not_worse, tuner.replay_with)
    try:
        tuner.not_worse = lambda *a, **k: False          # refuse every restrict
        tuner.replay_with = lambda *a, **k: {"closed_net": 0.0,
                                             "unrealized": 0.0}
        _bars, _prov, log = tuner.consume_proposals(
            proposals, [1, 2], {}, {}, lens_fresh=False)
    finally:
        tuner.not_worse, tuner.replay_with = saved

    bad = [line for line in log if "DISQUALIFIED" in line]
    assert not bad, (
        "the scout tuner rejected our declared direction as wrong:\n  "
        + "\n  ".join(bad))
    assert log, ("consume_proposals saw nothing — the cross-check would pass "
                 "vacuously; check the lever names reached PROPOSAL_TAKER")


def test_levers_no_consumer_reads_are_declared_not_silently_proposed():
    """tp/sl are deliberately absent from the tuner's PROPOSAL_TAKER ('their
    direction semantics are not monotone'). Proposing them anyway would fill
    the channel with entries nothing reads — the registered-but-inert shape
    I18 names — so they are dropped AND named on the payload.

    THE GENOTYPE HERE MOVES tp AND sl OFF THE TAKER'S DEFAULTS ON PURPOSE, and
    that is not cosmetic: a mutation round caught this test passing vacuously
    against the live champion, whose tp (0.04) and sl (−0.03) happen to EQUAL
    the running config — so `v == cur` dropped them anyway and deleting the
    no-consumer filter entirely was invisible. The two reasons a lever can be
    absent have to be told apart by the case, not by the assertion."""
    gt = dict(LIVE_CHAMPION_GT, TAKE_PROFIT=0.05, STOP_LOSS=-0.02)
    assert gt["TAKE_PROFIT"] != tt.TAKE_PROFIT and gt["STOP_LOSS"] != tt.STOP_LOSS
    assert inc.is_enactable(gt), "the case must be in-cage or it refuses first"

    view = inc.champion_proposal(champ(gt), taker_defaults(),
                                 inc._tighter_map())
    assert view["levers"], "the case must otherwise propose, or this is vacuous"
    assert "taker.tp" not in view["levers"], (
        "taker.tp was proposed — the scout tuner's PROPOSAL_TAKER does not "
        "read it, so the entry occupies the channel and can never be gated")
    assert "taker.sl" not in view["levers"]
    assert {"taker.sl", "taker.tp"} <= set(view["no_consumer"]), view
    assert "taker.tp" in view["genotype_levers"], (
        "the full genotype must still be published — dropping it from the "
        "record too would hide what the champion actually is")


def test_a_champion_equal_to_the_running_config_proposes_nothing():
    view = inc.champion_proposal(champ(taker_defaults()), taker_defaults(),
                                 inc._tighter_map())
    assert view["levers"] == {}
    assert "running configuration" in view["refused"]


def test_the_kill_switch_reaches_the_wire(monkeypatch):
    monkeypatch.setattr(inc, "PROPOSE_ON", False)
    view = inc.champion_proposal(champ(LIVE_CHAMPION_GT), taker_defaults(),
                                 inc._tighter_map())
    assert view["levers"] == {}
    assert "INCUBATOR_PROPOSE=off" in view["refused"]


# ---------------------------------------------------------------------------
# 6. NO ROUTE TO REAL MONEY
# ---------------------------------------------------------------------------

def test_this_author_can_never_propose_on_the_live_lane():
    live = [n for n, spec in tuning.LEVERS.items()
            if spec.get("lane") == "lighter-live" or n.startswith("live.")]
    assert live, "no live levers in the registry — this control is vacuous"
    for lever in live:
        assert fprop._author_may_propose(lever, inc.PROPOSE_AUTHOR) is False, (
            f"{lever} is proposable by {inc.PROPOSE_AUTHOR} — this organ must "
            f"never have a path to real money")


def test_a_live_lever_from_this_author_is_dropped_at_the_channel(monkeypatch):
    """Not just the predicate — drive `propose` itself."""
    pstore = _Store()
    monkeypatch.setattr(fprop, "store", pstore)
    monkeypatch.setattr(fprop, "_cache", {"ts": 0.0, "payload": None})
    out = fprop.propose(
        {"live.funding.enter_apr": {"value": 0.0625, "direction": "restrict",
                                    "reason": "r", "evidence": "e"}},
        set_by=inc.PROPOSE_AUTHOR)
    assert out is None, ("a live.* proposal from the incubator survived the "
                         "author-lane filter")
    assert fprop.KEY not in pstore.saved


def test_the_author_name_is_one_the_channel_actually_admits():
    """The author string is not decoration: `fleet_proposals` binds each named
    organ to a lane, so borrowing another organ's identity would either
    silently attribute this organ's proposals to it or — worse, and silently —
    get them dropped. `impl-shortfall`, for instance, is bound to the LIVE lane
    and may not propose on `lighter-taker` at all."""
    assert fprop._author_may_propose("taker.momo_chg",
                                     inc.PROPOSE_AUTHOR) is True, (
        f"{inc.PROPOSE_AUTHOR!r} cannot propose on the taker lane — every "
        f"proposal this organ makes would be dropped at the channel, silently")
    declared = fprop.PROPOSAL_AUTHOR_LANES.get(inc.PROPOSE_AUTHOR)
    if declared is not None:                      # once someone declares it
        assert "lighter-taker" in declared, declared
    others = set(fprop.PROPOSAL_AUTHOR_LANES) - {inc.PROPOSE_AUTHOR}
    assert inc.PROPOSE_AUTHOR not in others, (
        "the incubator is proposing under another organ's declared identity")


def test_every_proposable_lever_is_on_a_shadow_lane():
    """Whatever the champion carries, the levers it can reach are shadow."""
    for gene, (lever, _grid) in inc.TAKER_GENES.items():
        lane = (tuning.LEVERS.get(lever) or {}).get("lane")
        assert lane == "lighter-taker", f"{gene} -> {lever} on lane {lane!r}"
