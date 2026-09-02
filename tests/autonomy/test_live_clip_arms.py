"""[(oc), 16-Aug] THE PER-ROW LIVE CLIP ARMS, end to end.

`(nj)` gave 🙏 Avo LIVE its own clip lever (`live.avo.clip_scale`) so the
board could size it without moving 💸 the Farmer. Two consumers did not
follow, and both were found by the re-run sweep and independently verified:

  1. `fleet_proprioception.group_of` matched the SHARED name exactly, so the
     new arm fell through to the generic `live.` group — which CAN return a
     HURTING verdict, graded over LIVE_ROWS, i.e. off the FARMER's trades.
     Two defects in one fall-through: a clip lever escaping the clip rule
     (per-trade % is invariant to clip size, which is why `live-clip` grades
     `recorded`), and one book's lever judged on another book's record.
  2. `evidence_board.live_clip_grade` read `live.clip_scale` unconditionally,
     so Avo's ladder was gated on the Farmer's verdict.

Plus the roster half: both organs share EVBOARD_LIVE_ROWS as a kill switch,
but their DEFAULTS had diverged — the board gained the second live row at
`(ma)` and proprioception did not.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import evidence_board as eb        # noqa: E402
import fleet_proprioception as fp  # noqa: E402

AVO = "freqtrade-avo-maria-lighter"
FARMER = "perps-funding-lighter-lighter"   # RETIRED live arm (ta)
GEORGIA = "freqtrade-georgia-lighter"      # took its sub-account (ta)


def test_every_live_clip_arm_routes_to_the_clip_rule():
    assert fp.group_of("live.clip_scale") == "live-clip"
    assert fp.group_of("live.avo.clip_scale") == "live-clip", (
        "a per-row clip arm fell through to the generic live group, which can "
        "return HURTING off another book's trades")
    # a non-clip live lever must NOT be captured by the widened test
    assert fp.group_of("live.funding.enter_apr") == "live-funding"
    assert fp.group_of("live.something_else") == "live"


def test_the_two_organs_agree_on_who_is_live_by_default():
    """A shared kill switch with divergent defaults is not a shared roster."""
    assert fp.LIVE_ROWS == eb.LIVE_ROWS, (fp.LIVE_ROWS, eb.LIVE_ROWS)
    # [2026-08-22 (tb)] the cohort follows the MONEY, not the history: 💸 the
    # Farmer's live arm retired at (ta) and 🔮 georgia took its sub-account.
    # Both halves are asserted — a retired row must be GONE, not merely joined
    # by its successor, or the board keeps sizing a book that cannot trade.
    # [2026-09-02 (wl)] the money moved again: georgia's live arm retired at
    # (wg) and her ~$220 went to 👩 mum, so georgia joins the GONE half and
    # mum the present half — the same both-halves shape, one generation on.
    assert {AVO, "freqtrade-mum-lighter"} <= fp.LIVE_ROWS
    assert GEORGIA not in fp.LIVE_ROWS and GEORGIA not in eb.LIVE_ROWS
    assert FARMER not in fp.LIVE_ROWS and FARMER not in eb.LIVE_ROWS


def _prop(verdicts):
    import datetime as dt
    return {"updated": dt.datetime.now(dt.timezone.utc).isoformat(),
            "ttl_sec": 2700, "verdicts": verdicts}


def test_each_row_is_graded_on_its_OWN_arm():
    state = _prop({"live.clip_scale": {"verdict": "hurting"},
                   "live.avo.clip_scale": {"verdict": "helping"}})
    assert eb.live_clip_grade(state, bot=FARMER) == "hurting"
    assert eb.live_clip_grade(state, bot=AVO) == "helping", (
        "Avo's ladder read the Farmer's verdict — another book's grade could "
        "release its lever or hold its top step")


def test_an_unknown_row_degrades_to_the_shared_lever():
    """Fail-safe: pre-(nj) behaviour for anything not in the arm map."""
    state = _prop({"live.clip_scale": {"verdict": "hurting"}})
    assert eb.live_clip_grade(state, bot="some-new-live-row") == "hurting"
    assert eb.live_clip_grade(state) == "hurting"      # no bot => shared


def test_the_board_reads_the_arm_inside_the_per_row_loop():
    """AST: the grade must be computed with a bot argument, not hoisted."""
    import ast
    src = (Path(__file__).resolve().parents[2] / "evidence_board.py").read_text()
    calls = [n for n in ast.walk(ast.parse(src))
             if isinstance(n, ast.Call)
             and getattr(n.func, "id", None) == "live_clip_grade"]
    run_calls = [c for c in calls if c.keywords or len(c.args) > 1]
    assert run_calls, "live_clip_grade is never called with a row — the "\
                      "per-row arm is not wired"
