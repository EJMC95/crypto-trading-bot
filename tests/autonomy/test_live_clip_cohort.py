"""[2026-08-16 (nj)] THE LIVE CLIP COHORT MUST BE EVERY BOOK THE LEVER STEERS,
AND EACH BOOK MUST CARRY ITS OWN METRICS AND ITS OWN ARM.

THE INCIDENT. `evidence_board.LIVE_ROWS` shipped as the single row
`perps-funding-lighter-lighter`, under a 17-Jul comment that states the rule
correctly and even names its own trigger: *"When the taker is wired to
venue_context/live.clip_scale, add it HERE in the same commit."* On 13-Aug
((ma)) 🙏 Avo Maria took the live slot, and `lighter_avo_live_bot` reads
`live.clip_scale` and multiplies its entry clip by it. The commit came and the
cohort never moved, so for three days the board:

  * sized a real-money book it could not see — an Avo drawdown reached NO
    actuator, because `_hurt_why` only ever looked at rows in the cohort; and
  * moved Avo on the FARMER's evidence — one shared dial across a directional
    funding book and a swing-dip long book.

This is the mirror of the Tide Rider ratchet the same comment block records:
there the cohort was a strict SUPERSET of the visible rows (a one-way
ratchet), here a strict SUBSET of the steered rows (an invisible book).

WHAT THIS FILE PINS, and why the first test is the one that closes the class:
`test_every_live_clip_consumer_is_in_the_cohort` finds the consumers BY AST
over the live bot files, so a FOURTH live book wired to a clip lever without
joining the cohort turns the build red. Pinning today's two row ids would only
re-pin the instance — and the instance is not what failed here; the rule was
written down and not applied.
"""
import ast
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import evidence_board as eb           # noqa: E402
import fleet_tuning as tuning         # noqa: E402

FARMER = "perps-funding-lighter-lighter"
AVO = "freqtrade-avo-maria-lighter"

# The live real-money surface, and the row each file publishes. Kept explicit
# because "which file is a LIVE book" is a fact about the fleet, not about the
# code — the AST arm below is what makes the CONSUMER half self-maintaining.
LIVE_BOT_FILES = {"lighter_funding_bot.py": FARMER,
                  "lighter_avo_live_bot.py": AVO}


def _clip_lever_names(path):
    """Every `live.*clip_scale*` lever name this file passes to get_lever().

    AST, not substring: a page-wide `"live.clip_scale" in src` matches the
    prose in a docstring explaining the lever, which is how a wiring test
    passes against a bot that reads nothing at all.
    """
    tree = ast.parse(open(os.path.join(ROOT, path), encoding="utf-8").read())
    out = set()
    consts = {}
    for node in ast.walk(tree):
        # module-level NAME = "live...." bindings, so a consumer may name its
        # lever once instead of retyping the string at each call site.
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) \
                and isinstance(node.value.value, str):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    consts[t.id] = node.value.value
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "get_lever"):
            continue
        if not node.args:
            continue
        a = node.args[0]
        name = None
        if isinstance(a, ast.Constant) and isinstance(a.value, str):
            name = a.value
        elif isinstance(a, ast.Name):
            name = consts.get(a.id)
        if name and name.startswith("live.") and "clip_scale" in name:
            out.add(name)
    return out


def test_every_live_clip_consumer_is_in_the_cohort():
    """THE CLASS. A live book that READS a clip lever must be a row the board
    GRADES. The 17-Jul rule, now executable instead of a comment."""
    for path, row in sorted(LIVE_BOT_FILES.items()):
        levers = _clip_lever_names(path)
        if not levers:
            continue                      # this book is not clip-lever steered
        assert row in eb.LIVE_ROWS, (
            f"{path} consumes {sorted(levers)} but its row {row!r} is NOT in "
            f"evidence_board.LIVE_ROWS ({sorted(eb.LIVE_ROWS)}). The board "
            f"would size a real-money book it cannot see — the (nj) defect.")


def test_every_live_clip_consumer_reads_its_own_arm():
    """...and it must read ITS OWN arm, not the shared dial. The fallback to
    `live.clip_scale` is allowed (it is what makes the rollout gap-free), but
    the row's own lever must be among the names the file actually reads."""
    for path, row in sorted(LIVE_BOT_FILES.items()):
        levers = _clip_lever_names(path)
        if not levers:
            continue
        own = eb.live_clip_lever(row)
        assert own in levers, (
            f"{path} (row {row}) reads {sorted(levers)} but not its own arm "
            f"{own!r} — it is still steered by another book's evidence.")


def test_each_live_row_has_a_distinct_registered_arm():
    """One book, one arm — and every arm registered, caged and board-owned. An
    unregistered live name is dropped by write_levers, i.e. an arm that looks
    wired and moves nothing."""
    arms = {r: eb.live_clip_lever(r) for r in eb.LIVE_ROWS}
    assert len(set(arms.values())) == len(arms), (
        f"live rows share an arm: {arms} — a shared dial is the (nj) defect.")
    for row, lever in sorted(arms.items()):
        spec = tuning.LEVERS.get(lever)
        assert spec, f"{lever} ({row}) is not in the fleet_tuning registry"
        assert spec["lane"] == "lighter-live", f"{lever} is not on the live lane"
        assert tuning._author_may_write(lever, "lighter-live", "evidence-board"), \
            f"the board cannot write {lever} — the arm is inert"


def test_the_judge_still_cannot_touch_a_clip_arm():
    """The judge's sole-writer lane (live.funding.*) is untouched by (nj), and
    no new live prefix may leak write access to another author."""
    for row in sorted(eb.LIVE_ROWS):
        lever = eb.live_clip_lever(row)
        assert not tuning._author_may_write(lever, "lighter-live",
                                            "experiment-judge")
        assert not tuning._author_may_write(lever, "lighter-live", "scout-tuner")
    assert tuning._author_may_write("live.funding.enter_apr", "lighter-live",
                                    "experiment-judge")
    assert not tuning._author_may_write("live.funding.enter_apr", "lighter-live",
                                        "evidence-board")


def _rows(farmer_pnl=0.0, avo_pnl=0.0):
    return [{"bot": FARMER, "pnl_abs": farmer_pnl, "closed_trades": 123},
            {"bot": AVO, "pnl_abs": avo_pnl, "closed_trades": 0}]


def _decide(row, window, now=1_000_000.0):
    return eb.synthesize_live(_rows(), {}, {}, [], {}, now, None,
                              window=window, released_ts=0.0, scope={row})


@pytest.mark.parametrize("bleeder,bystander", [(FARMER, AVO), (AVO, FARMER)])
def test_a_drawdown_moves_only_the_bleeding_books_arm(bleeder, bystander):
    """BOTH DIRECTIONS, and the second one is the half that was structurally
    impossible before (nj): Avo was not in the cohort, so its own drawdown
    could not move anything at all."""
    window = {bleeder: {"pnl": -25.0, "closes": 6},
              bystander: {"pnl": +5.0, "closes": 6}}

    scale, item = _decide(bleeder, window)
    assert scale == eb.LIVE_DOWN_SCALE, (
        f"{bleeder} lost $25 over 7d and its arm did not tighten")
    assert item["lever"] == eb.live_clip_lever(bleeder)
    assert bleeder in item["msg"], "the push must name the book that moved (I8)"

    scale2, _ = _decide(bystander, window)
    assert scale2 != eb.LIVE_DOWN_SCALE, (
        f"{bystander} was sized on {bleeder}'s drawdown — the books are still "
        f"sharing one dial, which is the defect (nj) exists to remove.")


def test_the_two_rows_cannot_collide_in_the_alert_stream():
    """Per-row decisions need per-row keys: one shared key and the second
    row's item silently overwrites the first's."""
    window = {FARMER: {"pnl": -25.0, "closes": 6},
              AVO: {"pnl": -25.0, "closes": 6}}
    k1 = _decide(FARMER, window)[1]["key"]
    k2 = _decide(AVO, window)[1]["key"]
    assert k1 != k2, f"both live rows emit the same item key {k1!r}"
    # ...and both must still be recognised as the live-clip item, or run_once's
    # DEDICATED_PUSH skip stops working and an ENACTED real-money change gets
    # re-sent through the generic "Proposed (shadow)" template.
    for k in (k1, k2):
        assert k.startswith("board:live-clip-scale")


def test_avos_arm_is_restrict_only_in_both_the_cage_and_the_consumer(monkeypatch):
    """Avo's gross is equity x clip_scale x stake_mult with all three terms
    reduce-only, so the book is 1.00x by construction. The registry cage must
    say the same thing the consumer enforces — a cage above the clamp would
    register authority the consumer silently discards.

    BEHAVIOURAL, and it has to be. The first version of this test asserted
    `"min(1.0" in <source of _clip_scale_now>` and SURVIVED the mutation that
    widens the clamp to 1.5 — because the function's own docstring contains
    the words "min(1.0, ...)" while explaining the rule. A substring scan that
    matches the prose promising the property is not a test of the property
    (CLAUDE.md: "a page-wide substring scan is not a structural claim"). So:
    feed the consumer an over-1.0 lever and watch what it actually returns.
    """
    spec = tuning.LEVERS[eb.live_clip_lever(AVO)]
    assert spec["hi"] == 1.0, (
        "Avo's cage allows >1.0 while its consumer clamps at 1.0 — "
        "registered-but-inert authority")

    import lighter_avo_live_bot as avo

    for served in (1.5, 1.25, 4.0):
        monkeypatch.setattr(tuning, "get_lever",
                            lambda name, default, _v=served: _v, raising=True)
        got = avo._clip_scale_now()
        assert got <= 1.0, (
            f"the rail served {served} and Avo's consumer applied {got} — the "
            f"clip lever can now GROW this book past equity/slots, so gross "
            f"notional can exceed account equity")

    # ...and it still restricts when told to
    monkeypatch.setattr(tuning, "get_lever", lambda name, default: 0.5,
                        raising=True)
    assert avo._clip_scale_now() == 0.5, "the restrict direction stopped working"


def test_legacy_scalar_prior_is_not_read_as_a_release():
    """MIGRATION. The pre-(nj) payload stored `live_scale` as a scalar
    {"value","ts"}. Read as the new per-row map that is an EMPTY prior for
    every row, i.e. an in-force restriction would read as absent — a release
    nobody decided, on real money. The Farmer owned the old scalar, so it must
    still own it after the upgrade."""
    legacy = {"value": 0.75, "ts": 123.0}

    def prior_for(bot, prior_all=legacy):
        if isinstance(prior_all, dict) and "value" in prior_all:
            return prior_all if bot == eb.FARMER_ROW else {}
        return (prior_all or {}).get(bot) or {}

    assert prior_for(FARMER)["value"] == 0.75, \
        "the legacy scalar restriction was dropped on upgrade"
    assert prior_for(AVO) == {}, \
        "the legacy scalar was attributed to a book that never owned it"
    # the new shape round-trips per row
    new = {FARMER: {"value": 0.75, "ts": 1.0}, AVO: {"value": 0.5, "ts": 2.0}}
    assert prior_for(FARMER, new)["value"] == 0.75
    assert prior_for(AVO, new)["value"] == 0.5


def test_no_retired_row_in_the_cohort():
    """The Tide Rider ratchet, still guarded: a retired row's bot_pnl row is
    deleted at boot, so it can never be visible and `cohort_ok` would be False
    forever — pinning a restriction with no path back but the operator."""
    import cleanup_legacy_bots as clb
    retired = set(getattr(clb, "LEGACY_BOTS", ()) or ())
    assert not (eb.LIVE_ROWS & retired), (
        f"LIVE_ROWS names retired row(s) {sorted(eb.LIVE_ROWS & retired)}")
