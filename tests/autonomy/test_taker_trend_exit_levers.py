"""[(sf)] The breakout arm's TREND EXIT becomes reachable by the growth rail.

THE GAP. Under BULL_MODE `bull_exit()` routes breakout/breakoutup to a
DIFFERENT exit from every other lens — no TP cap, a wide hard stop, and a
trailing give-back off the peak. Both of its numbers were bare env literals
with no `fleet_tuning` entry, so the rail could move the fixed reversion
bracket that divergence uses (`taker.tp` / `taker.sl`) and could not touch the
exit that actually binds the taker's best long lens:

    long-breakoutup_hold   n=27  +$23.77  (+1.412%/trade)
    long-breakoutup_trail  n=18   -$9.59  (-1.722%/trade)

That is I18 — the binding constraint must be a reachable lever — and it was
not one.

REGISTERING MOVES NOTHING, and that is the point (the `disloc.exit_bps`
idiom). Both defaults are today's values. The widening these knobs invite was
MEASURED AND WITHHELD on the same day: the trail's whole 6%-to-OFF effect
(~0.10pp) is smaller than the harness's own calibration drift (+0.508pp), and
the clock's 48h->96h gain falls from +0.78pp to +0.07pp once HYPE is dropped.
What the rail gains is the ability to walk them through the scout tuner's
replay gate, hourly, on evidence — instead of a session hand-setting a number
two measurements refused.
"""
import pytest

pytestmark = pytest.mark.autonomy

import fleet_tuning as FT              # noqa: E402
import lighter_ticket_taker as TT      # noqa: E402


# ------------------------------------------------------------------- reach

@pytest.mark.parametrize("lever,attr,default", [
    ("taker.brk_trail", "BRK_TRAIL", 0.06),
    ("taker.brk_sl", "BRK_SL", -0.07),
])
def test_the_trend_exit_knob_is_registered_caged_and_consumed(lever, attr,
                                                              default):
    lev = FT.LEVERS[lever]
    assert lev["lane"] == "lighter-taker", lev
    assert lev["env_default"] == default == getattr(TT, attr), (
        "the registry default must be the value the consumer actually runs")
    # [(sf)] ONE-SIDED at the default, deliberately — see
    # tests/autonomy/test_breakoutup_ratchet.py. While the actuator that would
    # move these is blind to the lens they govern, its restrict path enacts for
    # free and its expand path is arithmetically impossible, so a cage with
    # room in the TIGHTEN direction is a one-way ratchet. All the room is in
    # the growth direction; that the restrictive end sits AT the default is
    # asserted there, and here we only require the cage is not welded shut.
    assert lev["lo"] <= default <= lev["hi"] and lev["lo"] != lev["hi"], (
        f"{lever} cage is degenerate: {lev}")
    assert (lever, attr) in TT.TUNABLE, (
        f"{lever} is registered but not in TUNABLE — registered-but-inert, "
        "the exact failure the lighter-books lane was created to prevent")


def test_registering_them_moved_nothing():
    """A lever whose registration changed the shipped value would be a
    widening wearing a reach costume."""
    assert TT.BRK_TRAIL == 0.06 and TT.BRK_SL == -0.07


def test_the_overlay_actually_reaches_bull_exit(monkeypatch):
    """The relationship that matters: a lever must change what the ROUTING
    returns, not merely a module attribute nothing reads. `bull_exit` is the
    single owner of the trend exit's params, so this drives it."""
    monkeypatch.setattr(TT, "BULL_MODE", True)
    monkeypatch.setattr(TT, "TT_VENUE", "lighter_shadow")

    class _T:
        @staticmethod
        def get_lever(name, default):
            return {"taker.brk_trail": 0.11,
                    "taker.brk_sl": -0.10}.get(name, default)

    monkeypatch.setattr(TT, "tuning", _T)
    monkeypatch.setattr(TT, "BRK_TRAIL", 0.06)
    monkeypatch.setattr(TT, "BRK_SL", -0.07)
    moved = TT.apply_tuning()
    assert moved.get("taker.brk_trail") == 0.11, moved
    assert moved.get("taker.brk_sl") == -0.10, moved
    bars, trail = TT.bull_exit("breakoutup")
    assert trail == 0.11, "the lever did not reach the routing"
    assert bars[1] == -0.10, bars


def test_the_reversion_lens_is_untouched_by_the_trend_knobs(monkeypatch):
    """divergence keeps its fixed bracket. If a breakout lever leaked into the
    reversion route it would be steering the ONE lens the live arm trades."""
    monkeypatch.setattr(TT, "BULL_MODE", True)
    monkeypatch.setattr(TT, "BRK_TRAIL", 0.11)
    monkeypatch.setattr(TT, "BRK_SL", -0.10)
    assert TT.bull_exit("divergence") == (None, 0.0)


# --------------------------------------------------------- and NOT real money

def test_the_live_arm_cannot_receive_them():
    """Structurally twice over: apply_tuning refuses the live venue outright,
    and the live arm is divergence-SHORT only, so the breakout branch of
    bull_exit is unreachable on real money even if a lever were set."""
    import ast
    import inspect
    tree = ast.parse(inspect.getsource(TT.apply_tuning).lstrip())
    guards = [n for n in ast.walk(tree)
              if isinstance(n, ast.If) and "lighter_live" in ast.unparse(n.test)]
    assert guards, "apply_tuning no longer refuses the live venue outright"
    assert any(isinstance(b, ast.Return) for g in guards for b in g.body), (
        "the live guard does not RETURN — levers would fall through to the "
        "overlay loop")
    assert set(TT.LIVE_SIDES) == {"divergence"}, (
        f"a lens beyond divergence reached LIVE_SIDES: {TT.LIVE_SIDES} — the "
        "breakout trend exit would then be live surface and these levers "
        "would need a live.* lane and a bound author")
    assert FT.LEVERS["taker.brk_trail"]["lane"] != "lighter-live"
    assert FT.LEVERS["taker.brk_sl"]["lane"] != "lighter-live"


# ------------------------------------------- receipts: the knobs can be MEASURED

class TestTheTrendExitRecordsWhatItsKnobsCut:
    """Registering a lever nobody can profile is the cage-nobody-can-measure
    failure `audit_lever_authority` exists to name — and it is exactly why both
    widenings had to be WITHHELD today rather than decided: the harness had to
    reconstruct from hourly candles what the bot already knew to the loop.

    The trail fires on GIVE-BACK from the peak; the stop on ADVERSE EXCURSION.
    Neither was ever written down.
    """

    def test_the_close_row_carries_both_quantities(self):
        e = TT._close_extra({"bars": {"tp": 0.04}, "peak_ret": 0.09,
                             "give_back": 0.055, "mae_ret": -0.021})
        assert e["peak_ret"] == 0.09
        assert e["give_back"] == 0.055
        assert e["mae_ret"] == -0.021

    def test_absent_is_UNKNOWN_and_never_zero(self):
        """A position closed on its first cycle, or a legacy row, never saw a
        mark. A grader reading a missing give_back as 0.0 would score it as
        'never gave anything back' — the best possible value — which would
        drag the profiled distribution toward the tight end of the cage."""
        e = TT._close_extra({"bars": {"tp": 0.04}})
        for k in ("peak_ret", "give_back", "mae_ret"):
            assert k not in e, f"{k} was defaulted rather than omitted"

    @pytest.mark.parametrize("junk", ["0.05", None, True, [], {}])
    def test_a_junk_value_is_dropped_not_stamped(self, junk):
        e = TT._close_extra({"bars": {}, "give_back": junk})
        assert "give_back" not in e, f"{junk!r} reached the ledger"

    def test_the_tracker_records_the_MAXIMUM_not_the_final(self):
        """The measurement that matters. A position that gave back 8% and then
        recovered to give back 1% at close TRIPPED an 6% trail on the way — a
        final-value stamp would record 1% and teach the profiler that the bar
        is never approached. Asserted on the update expressions, since they
        live inside main()'s manager loop."""
        import ast
        import inspect
        tree = ast.parse(inspect.getsource(TT.main).lstrip())
        got = {}
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign) or len(node.targets) != 1:
                continue
            t = node.targets[0]
            if not (isinstance(t, ast.Subscript)
                    and isinstance(t.slice, ast.Constant)
                    and t.slice.value in ("give_back", "mae_ret")):
                continue
            got[t.slice.value] = ast.unparse(node.value)
        assert set(got) == {"give_back", "mae_ret"}, got
        assert got["give_back"].startswith("max("), got["give_back"]
        assert "give_back" in got["give_back"], (
            "give_back does not accumulate against its own prior value — it "
            f"records a point, not a maximum: {got['give_back']}")
        assert got["mae_ret"].startswith("min("), got["mae_ret"]
        assert "mae_ret" in got["mae_ret"], got["mae_ret"]

    def test_the_receipts_reach_a_profiler_that_can_read_them(self):
        import scripts.audit_lever_authority as A
        t = A.QUANTITIES["taker.brk_trail"]
        assert t["extract"] == ("xfield", ("give_back", None)), t
        assert t["source"].endswith("lighter-ticket-taker-lshadow"), t
        s = A.QUANTITIES["taker.brk_sl"]
        assert s["extract"] == ("xfield", ("mae_ret", None)), s
        assert s["abs"] is True, (
            "the lever is signed and the excursion is negative — without abs "
            "the profile is compared against the wrong end of the cage")

    def test_the_new_extractor_reads_the_field_and_honours_its_scope(self):
        """The extractor is general — any book that stamps a decision quantity
        at close becomes profilable. It must also SCOPE: a bar governing the
        trail must not be profiled against positions the stop closed."""
        import scripts.audit_lever_authority as A
        import inspect
        src = inspect.getsource(A)
        assert 'elif kind == "xfield":' in src
        assert 'if suf and not str(r or "").endswith(suf):' in src, (
            "the reason-suffix scope is gone — the sample would pool exit "
            "families the bar does not govern")
