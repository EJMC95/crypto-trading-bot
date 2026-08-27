"""[(vf)] THE LIVE DOWN-REFLEX WAS CUTTING REAL BOOKS ON MONEY THEY DID NOT LOSE.

Two independent defects in one actuator — the evidence board's live-clip
restrict path, which shrinks REAL MONEY.

1. IT COUNTED HALT EVENTS AS TRADES. `fetch_realized_window` summed every
   `paper_trades` row in the window. Measured on 🔮 georgia, 27-Aug: her 7d
   window read **-$36.96** and the board cut her clip to 0.75x on it — but
   **-$34.83 of that was 10 forced-flatten rows spanning 6 events, five of them
   closed at ONE timestamp** (25-Aug 12:08). Her strategy's own 7d result was
   **-$2.13**. One bad afternoon, counted five times, shrank a live book. Those
   rows are already punished by the daily-loss rail that produced them.

2. ITS BAR WAS A FLAT $10 FROM WHEN THE LIVE BOOKS WERE ~$60 AT 1x. A single
   ORDINARY stop-out is now $24.79 on georgia, $30.00 on mum and **$68.11 on
   avo** — so the fleet's best book (+$16.46 over the same window) sat one
   designed loss from being cut. A trigger a book satisfies structurally is not
   a measurement (I7), and this one sat at a live actuator.

Deliberately NOT paired with a compensating new restriction: a halt already
costs the book its day and flattens it, and the daily-loss rail is what does
that. Cutting the clip for the same event is punishing it twice, which is the
miscount, not a safeguard.
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import evidence_board as eb        # noqa: E402
import fleet_bus as fb             # noqa: E402


def _row(bot, equity, gross_x, stop, slots, pnl_abs=0.0, closes=30):
    """The PUBLISHER's bot_pnl shape, carrying the fields the derived bar reads."""
    return {"bot": bot, "equity": equity, "pnl_abs": pnl_abs,
            "closed_trades": closes, "updated_at": eb._iso(),
            "extra": {"leverage": {"set": gross_x},
                      "policy": {"stoploss": -abs(stop)},
                      "cap_slots": slots}}


def _drive(row, window_pnl, closes=30, stripped=None):
    """Drive the REAL reflex. Returns the desired scale (None = no assertion).

    Driven rather than re-derived: the first draft of this file computed the
    bar arithmetic inline and BOTH mutations survived — reverting the derived
    bar and reverting the halt strip each left the suite green. A test that
    recomputes the thing it is pinning tests my arithmetic, not the code.
    """
    now = eb._now()
    fresh = eb._iso()
    fr = {"updated": fresh, "ttl_sec": 900, "light": "green",
          "clip_scale": 1.0}
    lm = {"updated": fresh, "stress": {"med": 5}}
    w = {row["bot"]: dict({"pnl": window_pnl, "closes": closes},
                          **(stripped or {}))}
    saved = eb.LIVE_ROWS
    eb.__dict__["LIVE_ROWS"] = {row["bot"]}
    try:
        scale, _item = eb.synthesize_live([row], fr, lm, [], {}, now, window=w)
        return scale
    finally:
        eb.__dict__["LIVE_ROWS"] = saved


GEORGIA = ("freqtrade-georgia-lighter", 247.90, 10.0, 0.05, 5)   # stop-out $24.79
AVO = ("freqtrade-avo-maria-lighter", 340.56, 10.0, 0.10, 5)     # stop-out $68.11


def test_georgia_is_no_longer_cut_for_an_afternoon_counted_five_times():
    """THE INCIDENT. Her 7d read -$36.96 and the board cut her to 0.75x; -$34.83
    of it was halt rows, 5 of them at ONE timestamp. Strategy-only: -$2.13."""
    r = _row(*GEORGIA, pnl_abs=-39.12)
    # as the window reads AFTER stripping forced flattens
    assert _drive(r, -2.13, stripped={"stripped_pnl": -34.83, "stripped_n": 10,
                                      "stripped_days": 2}) != eb.LIVE_DOWN_SCALE, \
        "georgia is still being cut on money her strategy did not lose"


def test_the_unstripped_window_WOULD_have_cut_her_the_counterfactual():
    """The other half of the same test: fed the raw -$36.96 the old window
    produced, the reflex DOES restrict. Without this the strip is unobservable
    — a fix whose before-state is untested is not pinned."""
    r = _row(*GEORGIA, pnl_abs=-39.12)
    assert _drive(r, -36.96) == eb.LIVE_DOWN_SCALE, \
        "the raw window no longer restricts — the counterfactual is gone"


def test_one_ordinary_stop_out_no_longer_cuts_the_best_book():
    """avo: one DESIGNED stop-out is $68.11 against the old flat $10 bar, so a
    single normal loss tripped the reflex on the fleet's best book."""
    r = _row(*AVO, pnl_abs=26.41)
    assert _drive(r, -30.0) != eb.LIVE_DOWN_SCALE, \
        "a loss well inside avo's own designed stop-out still cuts her"


def test_a_loss_PAST_the_designed_stop_is_still_cut_the_negative_control():
    """The loosening is not unconditional. A reflex that never fires is as
    useless as one that always does."""
    r = _row(*GEORGIA, pnl_abs=-39.12)
    assert _drive(r, -60.0) == eb.LIVE_DOWN_SCALE, \
        "a loss beyond the designed stop must still restrict"
    r2 = _row(*AVO, pnl_abs=26.41)
    assert _drive(r2, -140.0) == eb.LIVE_DOWN_SCALE, \
        "avo losing 2x her designed stop must still restrict"


def test_an_unreadable_row_keeps_the_flat_floor_fail_toward_today():
    """A row missing leverage/stoploss/slots falls back to the operator's flat
    bar — never to 'no bar'. The failure direction is the current rail."""
    r = {"bot": "x", "equity": 300.0, "pnl_abs": 0.0, "closed_trades": 30,
         "updated_at": eb._iso(), "extra": {}}
    saved = eb.LIVE_ROWS
    eb.__dict__["LIVE_ROWS"] = {"x"}
    try:
        now = eb._now()
        fr = {"updated": eb._iso(), "ttl_sec": 900, "light": "green",
              "clip_scale": 1.0}
        lm = {"updated": eb._iso(), "stress": {"med": 5}}
        w = {"x": {"pnl": -(eb.LIVE_DOWN_PNL + 1), "closes": 30}}
        s, _ = eb.synthesize_live([r], fr, lm, [], {}, now, window=w)
        assert s == eb.LIVE_DOWN_SCALE, \
            "an unreadable row stopped restricting at the flat floor"
    finally:
        eb.__dict__["LIVE_ROWS"] = saved


def test_the_board_actually_ASKS_for_the_strip_at_the_call_site():
    """WIRING, not the helper. These tests hand `window` in directly, so the
    one call site that passes `exclude_reasons` is never exercised by them —
    and a mutation deleting that argument SURVIVED the whole suite. That is the
    enacted-is-not-applied class: the strip would silently stop happening in
    production while every test stayed green.

    AST, not a substring — this file and the board both name the argument in
    prose."""
    import ast
    src = (ROOT / "evidence_board.py").read_text(encoding="utf-8")
    calls = [n for n in ast.walk(ast.parse(src))
             if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Attribute)
             and n.func.attr == "fetch_realized_window"]
    assert calls, "the board stopped reading the realized window at all"
    for c in calls:
        kw = {k.arg for k in c.keywords}
        assert "exclude_reasons" in kw, (
            "the board asks for the RAW window again — halt events are back in "
            "the sum, and one flatten counted five times shrinks a live book")


def test_the_strip_families_reach_the_call_as_the_fleets_own_tuple():
    """And the argument must carry the fleet's vocabulary, not an empty list
    (which would satisfy the wiring check above while stripping nothing)."""
    import ast
    src = (ROOT / "evidence_board.py").read_text(encoding="utf-8")
    for c in [n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
              and n.func.attr == "fetch_realized_window"]:
        for k in c.keywords:
            if k.arg == "exclude_reasons":
                assert isinstance(k.value, ast.Name) and \
                    k.value.id == "_STRIP_EXITS", \
                    "exclude_reasons is no longer the shared _STRIP_EXITS"
    assert set(eb._STRIP_EXITS) >= {"daily_loss", "kill_switch"}
