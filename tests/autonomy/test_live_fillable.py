"""[(aan)] THE GATE SAID READY ON A POLICY NO LIVE ARM COULD HAVE RUN.

On 2026-09-10 🎫 `lighter-ticket-taker-lshadow` had read `ready: True`, 6 of 6
bars, for six days, and Eamon said *"i will put the two books that are ready
live tomorrow"*. Its graded era, split by entry family:

    long-breakoutup    n=162   +1.382%/trade   t=+2.70   net +$134.00
    short-divergence   n= 46   -0.788%/trade   t=-1.31   net  -$17.35

`lighter_ticket_taker.LIVE_LENSES` is `{"divergence"}` and `LIVE_SIDES` is
`{"divergence": {"short"}}`. So **77.9% of the sample that passed the six bars
comes from a family no live arm may fill**, and the one family it may fill is
the loser — which the book's OWN published `lens_veto: ["dip","divergence"]`
has also vetoed. Driving the module's own gates against the live payload, all
ten (lens, side) pairs block: 8 at the lens allow-list, 1 at the side
allow-list, `short-divergence` at the veto. **A live arm would have filled
nothing.**

The gate was not wrong — it grades the SHADOW policy honestly, and the shadow
trades five lenses on both sides. What was missing is that nothing put the
graded sample and the live allow-list side by side, so `ready` read as "safe
to switch on".

`veto_split` is the near-miss, and it pointed the OTHER WAY: it keys on the
shadow's own veto set, so it labels the 162 `still_tradeable` (+1.382%,
t=+2.70) — the flattering subset, and the one no live arm can produce. `(yn)`
shipped it saying the number a go-live decision needs is the one "for the
configuration the book will actually run"; for a PROMOTION that configuration
is the live arm's, and there the subset is exactly inverted.

THE THREE REFUSALS ARE THE SAFETY, and every one is asserted below: it moves
no sample, no era and no bar. `ready` still means what it always meant — the
six bars pass on the graded sample — because that sample is the shadow book's
record and the shadow book earned it.
"""
import ast
import pathlib
from datetime import datetime, timedelta, timezone

import pytest

pytestmark = pytest.mark.autonomy

import sys
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import golive_readiness as G                                   # noqa: E402

T0 = datetime(2026, 8, 1, tzinfo=timezone.utc)

#: the taker's real live allow-list, in the shape the book publishes it
TAKER_LIVE = {"lenses": ["divergence"],
              "sides": {"breakout": [], "breakoutup": [], "dip": [],
                        "divergence": ["short"], "momentum": []}}


def row(pct, ab, i, tag, pair="BTC/USDC"):
    return (pct, ab, T0 + timedelta(hours=i), T0 + timedelta(hours=i - 1),
            {}, tag, pair)


def taker_era():
    """The measured shape: a big winner the live arm may never fill, and a
    small loser that is all it may."""
    win = [row(0.02, 2.0, i, "long-breakoutup") for i in range(10)]
    lose = [row(-0.01, -1.0, 20 + i, "short-divergence") for i in range(6)]
    return win + lose


# --------------------------------------------------------------------------
# the declaration
# --------------------------------------------------------------------------
def test_the_live_allow_list_is_read_from_the_books_own_publish():
    lp = G.published_live_policy({"live_policy": TAKER_LIVE})
    assert lp["lenses"] == ("divergence",)
    assert lp["sides"]["divergence"] == ("short",)
    assert G.published_live_policy(
        {"caps": {"live_policy": TAKER_LIVE}})["lenses"] == ("divergence",)


@pytest.mark.parametrize("junk", [
    {}, None, {"live_policy": None}, {"live_policy": "divergence"},
    {"live_policy": {"lenses": "divergence", "sides": {}}},
    {"live_policy": {"lenses": ["ok"], "sides": []}},
    {"live_policy": {"lenses": [1], "sides": {}}},
    {"live_policy": {"lenses": ["ok", ""], "sides": {}}},
    {"live_policy": {"lenses": ["ok"], "sides": {"ok": "short"}}},
    {"live_policy": {"lenses": ["ok"], "sides": {"ok": [2]}}},
    {"live_policy": {"lenses": ["ok"], "sides": {"": ["short"]}}},
    {"live_policy": {"sides": {}}},
])
def test_an_unpublished_or_malformed_live_policy_is_None_not_permissive(junk):
    """I6, and this is THE load-bearing direction. `None` must never be read
    as 'a live arm may fill everything' — that reads a SILENCE as a
    PERMISSION, and the thing on the other side of it is real money.

    Mutation: return `{"lenses": (), "sides": {}}` (or anything non-None) from
    the guard clauses => this reddens.
    """
    assert G.published_live_policy(junk) is None


def test_an_explicitly_empty_allow_list_is_a_declaration_not_a_silence():
    """A book publishing `lenses: []` HAS answered: a live arm may fill
    nothing. That is the opposite of not answering, and the split must run."""
    lp = G.published_live_policy({"live_policy": {"lenses": [], "sides": {}}})
    assert lp == {"lenses": (), "sides": {}}
    lf = G.live_fillable(taker_era(), lp)
    assert lf["inert"] is True and lf["unfillable"]["n"] == 16
    assert lf["blocked_by"]["lens_not_allowed"] == 16


# --------------------------------------------------------------------------
# the split
# --------------------------------------------------------------------------
def test_it_separates_what_a_live_arm_may_fill_from_what_it_may_not():
    lp = G.published_live_policy({"live_policy": TAKER_LIVE})
    lf = G.live_fillable(taker_era(), lp)
    assert lf["unfillable"]["n"] == 10 and lf["allowed"]["n"] == 6
    assert lf["blocked_by"]["lens_not_allowed"] == 10
    # the winner is the UNFILLABLE side — the whole point
    assert lf["unfillable"]["mean_pct"] > 0 > lf["allowed"]["mean_pct"]
    assert "LIVE arm" in lf["why"]


def test_the_side_allow_list_blocks_independently_of_the_lens_one():
    """`LIVE_SIDES` is the twin of `LIVE_LENSES` and is a SEPARATE gate: a
    lens on the allow-list may still be refused on the wrong side.

    Mutation: drop the `side not in allow_sides` branch => this reddens.
    """
    lp = G.published_live_policy({"live_policy": TAKER_LIVE})
    rows = ([row(0.01, 1.0, i, "long-divergence") for i in range(4)]
            + [row(-0.01, -1.0, 10 + i, "short-divergence") for i in range(3)])
    lf = G.live_fillable(rows, lp)
    assert lf["blocked_by"]["side_not_allowed"] == 4
    assert lf["blocked_by"]["lens_not_allowed"] == 0
    assert lf["allowed"]["n"] == 3


def test_the_veto_has_a_different_lifetime_from_the_allow_list():
    """Two gates, two lifetimes, reported as two numbers. The allow-list is
    structural (two deliberate edits to a real-money module); a veto lifts on
    the lens's own next evidence ((yn)). Folding them into one number would
    report a reversible switch as a permanent property.

    Mutation: let a vetoed row into `effective` => this reddens.
    """
    lp = G.published_live_policy({"live_policy": TAKER_LIVE})
    rows = taker_era()
    open_ = G.live_fillable(rows, lp, vetoed=None)
    assert open_["allowed"]["n"] == 6 and open_["effective"]["n"] == 6
    assert open_["inert"] is False and open_["vetoed"] is None
    shut = G.live_fillable(rows, lp, vetoed=("dip", "divergence"))
    assert shut["allowed"]["n"] == 6, "the allow-list does not move"
    assert shut["effective"]["n"] == 0, "the veto empties what it may fill"
    assert shut["blocked_by"]["lens_vetoed"] == 6
    assert shut["inert"] is True


def test_the_measured_taker_verdict_reproduces():
    """The live payload's own numbers, at the era's real proportions."""
    lp = G.published_live_policy({"live_policy": TAKER_LIVE})
    rows = ([row(0.01382, 0.827, i, "long-breakoutup") for i in range(162)]
            + [row(-0.00788, -0.377, 500 + i, "short-divergence")
               for i in range(46)])
    lf = G.live_fillable(rows, lp, vetoed=("dip", "divergence"))
    assert lf["unfillable"]["n"] == 162 and lf["allowed"]["n"] == 46
    assert lf["effective"]["n"] == 0 and lf["inert"] is True
    assert "77.9%" in lf["why"] and "EMPTY" in lf["why"]


def test_a_book_whose_live_arm_matches_its_shadow_says_nothing():
    """`why` is set only when the split is DECISION-RELEVANT — the
    `class_split` rule. A book with no live/shadow asymmetry must not add
    noise to the docket."""
    lp = G.published_live_policy(
        {"live_policy": {"lenses": ["breakoutup"],
                         "sides": {"breakoutup": ["long"]}}})
    clean = [row(0.02, 2.0, i, "long-breakoutup") for i in range(6)]
    lf = G.live_fillable(clean, lp)
    assert lf["unfillable"]["n"] == 0 and lf["inert"] is False
    assert "why" not in lf


def test_an_unreadable_tag_returns_None_rather_than_a_guess():
    """`veto_split`'s rule, for its reason (I6): a wrong split riding on a
    go-live decision is worse than no split.

    Mutation: classify an unparseable tag as unfillable => this reddens.
    """
    lp = G.published_live_policy({"live_policy": TAKER_LIVE})
    assert G.live_fillable(taker_era() + [row(0.01, 1.0, 40, "untagged")],
                           lp) is None
    assert G.live_fillable([(0.01, 1.0, T0, T0, {}, None, "X")], lp) is None
    assert G.live_fillable([(0.01, 1.0, T0, T0, {}, "-divergence", "X")],
                           lp) is None
    assert G.live_fillable(taker_era(), None) is None
    assert G.live_fillable([], lp) is None


def test_the_tag_accessor_is_overridable_like_its_siblings():
    lp = G.published_live_policy({"live_policy": TAKER_LIVE})
    rows = [(0.02, 2.0, T0, T0, {}, None, "BTC", "long-breakoutup")]
    lf = G.live_fillable(rows, lp, tag_of=lambda r: r[7])
    assert lf["unfillable"]["n"] == 1


# --------------------------------------------------------------------------
# the three refusals — this is the safety
# --------------------------------------------------------------------------
def test_it_moves_no_bar():
    """Mutation: add `live_fillable` to BAR_NAMES or to grade() => red.

    An INERT live arm must not make the shadow book un-READY: the six bars
    grade the shadow's record and the shadow earned them.
    """
    assert "live_fillable" not in G.BAR_NAMES
    rows = taker_era()
    s = G.stats([(r[0], r[1], r[2]) for r in rows])
    before = (G.grade(s), G.bar_map(s))
    lp = G.published_live_policy({"live_policy": TAKER_LIVE})
    s["live_fillable"] = G.live_fillable(rows, lp, vetoed=("divergence",))
    assert s["live_fillable"]["inert"] is True
    assert (G.grade(s), G.bar_map(s)) == before
    src = pathlib.Path(G.__file__).read_text()
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == "grade")
    assert "live_fillable" not in ast.unparse(fn)


def test_it_moves_no_sample():
    rows = taker_era()
    n_before = len(rows)
    lp = G.published_live_policy({"live_policy": TAKER_LIVE})
    lf = G.live_fillable(rows, lp, vetoed=("divergence",))
    assert len(rows) == n_before
    assert lf["allowed"]["n"] + lf["unfillable"]["n"] == n_before


# --------------------------------------------------------------------------
# the wiring — a substring test is not a wiring test
# --------------------------------------------------------------------------
def _calls(src, name):
    return [n for n in ast.walk(ast.parse(src))
            if isinstance(n, ast.Call) and getattr(n.func, "id", None) == name]


def test_the_publish_path_attaches_it_from_the_era_owner():
    """Mutation: pass `_lens_veto.get(bot)` (or a re-derived sample) as the
    policy, or attach it to the all-time rows => this reddens."""
    src = pathlib.Path(G.__file__).read_text()
    calls = _calls(src, "live_fillable")
    assert calls, "live_fillable is never called"
    got = [ast.unparse(c) for c in calls]
    assert any("scoped_rows" in g and "_live_policy.get(bot)" in g
               and "vetoed=_lens_veto.get(bot)" in g for g in got), got
    assert any("published_live_policy" in ast.unparse(c)
               for c in _calls(src, "published_live_policy"))


def test_book_payload_publishes_it():
    """Asserted on the SUBSCRIPT NODE, not on a quoted substring: ast.unparse
    normalises quote style, so `'"live_fillable"' in unparse(fn)` is a check
    that inspects nothing (the (po) rule, met while writing this file)."""
    src = pathlib.Path(G.__file__).read_text()
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == "book_payload")
    targets = [ast.unparse(t) for n in ast.walk(fn)
               if isinstance(n, ast.Assign) for t in n.targets]
    assert "out['live_fillable']" in targets, targets[-6:]


def test_the_taker_declares_by_ASKING_the_module_never_by_a_literal():
    """THE mutation that matters: a hard-coded `["divergence"]` in the payload
    drifts silently the day someone edits LIVE_LENSES, and the grader would
    then report a split for a policy the bot no longer runs.

    The declaration must CALL `allowed_lenses`/`allowed_sides` with the live
    mode.
    """
    src = (ROOT / "lighter_ticket_taker.py").read_text()
    tree = ast.parse(src)
    # Scoped to the `live_policy` VALUE NODE, never the whole module: the
    # module-wide substring form of this check SURVIVED its own mutation
    # round, because `allowed_lenses("lighter_live")` also appears in the
    # taker's selftest. A guard satisfied by an unrelated occurrence is the
    # (po) inspects-nothing rule inside the test written to prevent it.
    value = None
    for n in ast.walk(tree):
        if not isinstance(n, ast.Dict):
            continue
        for k, v in zip(n.keys, n.values):
            if isinstance(k, ast.Constant) and k.value == "live_policy":
                value = v
    assert value is not None, "the taker does not publish live_policy"
    inner = ast.unparse(value)
    assert "allowed_lenses('lighter_live')" in inner, \
        f"live_policy.lenses must ASK the module, not restate it: {inner}"
    assert "allowed_sides('lighter_live'" in inner, \
        f"live_policy.sides must ASK the module, not restate it: {inner}"


def test_the_card_renders_it_and_says_EMPTY_loudest():
    """The reader this exists for is a human about to switch a book on, so the
    verdict has to reach the 🚦 card — and the INERT state must be the loudest
    thing on it, not a tooltip.

    Mutation: drop the chip, or render `inert` in the same colour as the
    ordinary veto chip => this reddens.
    """
    src = (ROOT / "pnl_dashboard.py").read_text()
    tree = ast.parse(src)
    assert any(isinstance(n, ast.Constant) and n.value == "live_fillable"
               for n in ast.walk(tree)), "the card never reads live_fillable"
    assert "live arm fills NOTHING" in src
    # the inert branch must not share the veto chip's amber
    i = src.index("live arm fills NOTHING")
    around = src[i - 900:i]
    assert "#f85149" in around, "an empty live arm must render red, not amber"


def test_the_handoff_qualifies_a_READY_book_whose_live_arm_is_inert():
    """HANDOFF is the first thing a session reads (I11), and for six days it
    said `READY — 6/6 bars` about a book whose live arm could fill none of the
    closes that earned it.

    Mutation: drop the `inert` branch, or emit the note without the
    live_fillable read => this reddens.
    """
    import importlib
    ss = importlib.import_module("session_state")   # driven, not grepped
    bus = {"golive_readiness": {"books": {
        "inert-book": {"ready": True,
                       "bars": {"window": True, "closes": True, "mean": True,
                                "t": True, "halves": True, "maxdd": True},
                       "live_fillable": {"inert": True,
                                         "why": "its live arm fills nothing",
                                         "effective": {"n": 0},
                                         "unfillable": {"n": 208}}},
        "clean-book": {"ready": True,
                       "bars": {"window": True, "closes": True, "mean": True,
                                "t": True, "halves": True, "maxdd": True}}}}}
    out = ss.fleet_signals(pnl={"bots": []}, bus=bus)
    gate = " ".join(out.get("gate") or [])
    assert "inert-book" in gate and "FILL NOTHING" in gate.upper()
    assert "clean-book" in gate
    # the clean book must NOT be given the warning
    clean_seg = [g for g in out["gate"] if "clean-book" in g][0]
    assert "FILL NOTHING" not in clean_seg.upper()
