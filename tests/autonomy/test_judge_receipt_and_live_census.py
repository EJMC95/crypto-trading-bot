"""[(ye)/(yf)] TWO INSTRUMENTS THAT COULD NOT TELL 'BROKEN' FROM 'QUIET'.

Both were found on 4-Sep while answering why the live books had stopped
trading, and both sit on the path from shadow evidence to real money.

(ye) THE JUDGE ACCUSED AN ARM THAT WAS BEHAVING PERFECTLY. `arm_skew` reads
"0/N shadow closes carry a receipt -> the arm is not running this experiment",
and its denominator was every close in the window. But `extra.bars` is stamped
at ENTRY, so a position OPENED before the lever was applied can never carry it
however faithfully the arm runs. Measured: the judge held `mum-rsi-32` on
"0/3 shadow closes carry a receipt" while mum's shadow had last OPENED ~26h
earlier — before the experiment began. All three closes were pre-experiment.
The arm was applying the lever and had nothing to buy; the regime drought was
reported as broken plumbing, freezing the fleet's only promotion lane.

(yf) THE 24h DENOMINATOR EXISTED ONLY ON THE PAPER BOOKS. `(vm)` built
`census_24h` into `lighter_family_bot`, so it reached every $1,000 shadow and
NOT the live arms, which run `lighter_avo_live_bot` — the `(vh)` class. Mum's
shadow published the whole answer; her real-money row published nothing.
"""
import importlib

import experiment_judge as ej
import lighter_avo_live_bot as live


# --- (ye) the judge's receipt denominator ---------------------------------

def _row(bot, close_ts, open_ts, pct=0.05, bars=None):
    r = {"bot": bot, "profit_ratio": pct,
         "close_ts": ej.iso(close_ts), "open_ts": ej.iso(open_ts), "extra": {}}
    if bars is not None:
        r["extra"] = {"bars": bars}
    return r


def _window():
    t0 = ej.parse_ts("2026-09-01T00:00:00+00:00")
    return t0, t0 + 8 * 86400


def test_a_close_opened_before_the_lever_is_not_proof_the_arm_is_deaf():
    """THE LIVE DEFECT. Positions opened pre-lever CANNOT carry a receipt."""
    t0, end = _window()
    rows = ([_row(ej.SHADOW_BOT, t0 + i * 3600, t0 - 86400) for i in range(32)]
            + [_row(ej.LIVE_BOT, t0 + i * 7200, t0 + i * 7200, 0.002)
               for i in range(12)])
    v = ej.paired_eval(rows, t0, end, cand_levers={"xp.funding.enter_apr": 0.3})
    assert not v.get("arm_skew"), v
    assert v["n_shadow_opened_in_window"] == 0, v
    assert "not yet OPENED" in v["why"], v["why"]


def test_an_arm_that_DID_open_and_still_stamped_nothing_is_still_caught():
    """The positive control — the gate must not become unable to fire. A guard
    that never fires is trivially consistent and useless (I3 at a gate)."""
    t0, end = _window()
    rows = ([_row(ej.SHADOW_BOT, t0 + i * 3600, t0 + i * 3600) for i in range(32)]
            + [_row(ej.LIVE_BOT, t0 + i * 7200, t0 + i * 7200, 0.002)
               for i in range(12)])
    v = ej.paired_eval(rows, t0, end, cand_levers={"xp.funding.enter_apr": 0.3})
    assert v.get("arm_skew") is True, v
    assert v["n_shadow_opened_in_window"] == 32, v
    assert v["promote"] is False


def test_an_unreadable_open_stamp_cannot_vouch_either():
    """I8: unknown degrades to 'no evidence', never to 'the arm is deaf'."""
    t0, end = _window()
    rows = [_row(ej.SHADOW_BOT, t0 + i * 3600, t0 + i * 3600) for i in range(32)]
    for r in rows:
        r["open_ts"] = "not-a-timestamp"
    rows += [_row(ej.LIVE_BOT, t0 + i * 7200, t0 + i * 7200, 0.002)
             for i in range(12)]
    v = ej.paired_eval(rows, t0, end, cand_levers={"xp.funding.enter_apr": 0.3})
    assert not v.get("arm_skew"), v
    assert v["n_shadow_opened_in_window"] == 0, v


def test_opened_after_is_additive_every_existing_caller_is_unchanged():
    """`arm_trades` is used by the whole promotion path; the new filter must be
    inert unless asked for, or this fix would silently re-scope every bar."""
    t0, end = _window()
    rows = [_row(ej.SHADOW_BOT, t0 + i * 3600, t0 - 86400) for i in range(5)]
    assert len(ej.arm_trades(rows, ej.SHADOW_BOT, t0, end)) == 5
    assert len(ej.arm_trades(rows, ej.SHADOW_BOT, t0, end,
                             opened_after=t0)) == 0
    # AND the sharper half: a row whose open stamp is UNREADABLE must still
    # count for an ordinary caller. The new filter drops such rows (it cannot
    # vouch for them), so if it were ever active by default it would silently
    # shrink EVERY bar in the promotion path — including the live control arm,
    # whose rows predate the receipt entirely. A mutation flipping the default
    # from None to 0.0 survived the first round of this test, because 0.0 is
    # permissive on well-stamped rows and only bites on unreadable ones.
    bad = [_row(ej.SHADOW_BOT, t0 + i * 3600, t0 - 86400) for i in range(5)]
    for r in bad:
        r.pop("open_ts")
    assert len(ej.arm_trades(bad, ej.SHADOW_BOT, t0, end)) == 5, (
        "an unstamped open must not remove a close from an ordinary bar")


# --- (yf) census_24h on the real-money row --------------------------------

class _Store:
    def __init__(self, roll):
        self.roll, self.snapped = roll, []

    def census_window(self, bot, **kw):
        return dict(self.roll)

    def snapshot_census(self, bot, scan):
        self.snapped.append((bot, scan))
        return True


def _fresh_live():
    """A fresh module so the module-level rollup cache never leaks between
    tests — a cached rollup is exactly what `age_s` exists to expose."""
    return importlib.reload(live)


def test_the_live_row_publishes_the_24h_rollup_with_its_own_age():
    m = _fresh_live()
    m.store = _Store({"loops": 149, "no_signal": 2313, "both_terms_n": 36})
    out = m.census_series_extra("freqtrade-mum-lighter", 1000.0)
    assert out["census_24h"]["no_signal"] == 2313
    assert "age_s" in out["census_24h"], "a frozen cache must be visible (I1)"


def test_dark_history_omits_the_key_rather_than_publishing_zeros():
    """A zero-filled census reads as '300 loops, nothing refused', which is the
    loudest possible claim from no data (I8)."""
    m = _fresh_live()
    m.store = _Store({})
    assert m.census_series_extra("x", 1.0) == {}


def test_the_rollup_is_cached_and_its_age_grows_between_recomputes():
    m = _fresh_live()
    st = _Store({"loops": 10})
    m.store = st
    m.census_series_extra("b", 1000.0)
    later = m.census_series_extra("b", 1000.0 + m.CENSUS_ROLLUP_S / 2.0)
    assert later["census_24h"]["age_s"] > 0, "a cached rollup must age visibly"


def test_it_never_raises_into_the_live_loop():
    m = _fresh_live()

    class _Boom:
        def census_window(self, bot, **kw):
            raise RuntimeError("db down")
    m.store = _Boom()
    assert m.census_series_extra("b", 1.0) == {}


def test_the_scan_census_is_snapshot_under_the_bare_row_id():
    """The rails census lives under `<row>:rails`; the scan census must key on
    the BARE id or the two would pool into one meaningless series."""
    import ast
    import pathlib
    src = pathlib.Path(live.__file__).read_text()
    tree = ast.parse(src)
    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call)
             and ast.unparse(n.func).endswith("snapshot_census")]
    args = {ast.unparse(c.args[0]) for c in calls if c.args}
    assert "BOT_ROW" in args, (
        "the scan census is not snapshot under the bare row id", args)
    # The rails census snapshots through the `census_bot` PARAMETER of
    # `rails_cost`, with RAILS_CENSUS_BOT supplied at the call site — so the
    # collision property is about the CONSTANT, not this call's arg name.
    assert live.RAILS_CENSUS_BOT != live.BOT_ROW, (
        "the rails and scan censuses would pool into one meaningless series")
    assert live.RAILS_CENSUS_BOT.startswith(live.BOT_ROW + ":"), (
        "the rails key must stay a suffix of the row, not a free-floating id")
