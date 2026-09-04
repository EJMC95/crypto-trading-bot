"""[(ya)] TWO CENSUS GAUGES THAT COULD NOT ANSWER THE QUESTION THEY EXIST FOR.

Found 4-Sep answering Eamon's "bots aren't trading" on a fleet where nothing
was broken: 11 of 16 books were holding positions and the real money was up.
What the rows could NOT say was WHY the two live books were empty — and both
of the fields built for that were defective.

1 · `both_terms_n` DISAGREED WITH THE BAR PUBLISHED BESIDE IT. 👩 mum's
    REAL-MONEY row read `rsi_bar 36.0 · rsi_min 37.1 · both_terms_n 1`: no
    coin can pass a bar of 36 when the closest is 37.1, yet one was counted
    as passing. Cause, from the code and not from a guess: `last_enter` is a
    CACHED verdict (the loop `continue`s before `signals()` on a candle it has
    already acted on) while `rsi_bar` is read FRESH off `S.RSI_MAX` at census
    time, AFTER `apply_book_levers` has run every loop. A `live.mum.rsi_max`
    lever that opens, moves or EXPIRES between candle passes leaves the two
    sampled at different bars. (vm) built this field so "the census and the
    gate can never disagree about the cell" — prose could not enforce it,
    because the two halves are sampled at different TIMES ((tt)'s lesson: a
    defense that lives only in prose has not been written).

    It costs no trades — the real gate recomputes fresh each candle — but it
    corrupts the exact number a widening is priced from, which is what (vm)
    built it for.

2 · 🙏 avo's BINDING TERM HAD NO GAUGE AT ALL. Her rule is `e50>e200 AND
    rsi<42 AND close<lower-Bollinger AND v>0`. (st)/(vm) gauged RSI and the
    trend half; the BB dip — the one that actually binds in a rally — was
    computed by `signals()` and thrown away. Measured 4-Sep: `rsi_min 34.4`
    against `rsi_bar 42.0` (the RSI half MET) beside `verdicts {no_signal:
    39}`, with nothing on the row able to say which conjunct refused. Same
    class as (vm) at the sibling book.

Both are REPORTED — no gate reads either — and both are pinned on BOTH arms,
because (vh) is the standing lesson that a fix verified in one file and
shipped without asking which arm executes it reaches the $1,000 shadow and
not the real money.
"""
import lighter_family_bot as fam
import lighter_avo_live_bot as live


def _mum():
    for s in fam.STRATEGIES:
        if getattr(s, "UPTREND_BLOCKS", False):
            return s
    raise AssertionError("no UPTREND_BLOCKS carrier in STRATEGIES")


class _B:
    """Mirrors the family scan loop's own capture."""

    def __init__(self, strat):
        self.s = strat
        self.bot_id = strat.bot + "-lshadow"
        self.scan = {"scanned": 0, "opened": 0}
        self.last_rsi, self.last_uptrend, self.last_enter = {}, {}, {}
        self.last_enter_bar, self.last_bb, self.last_vel = {}, {}, {}
        self._rollup, self._rollup_at = None, 0.0


# --- 1 · the bar the verdict ran under ------------------------------------

def test_a_stale_bar_is_never_counted_as_a_current_pass():
    """THE DEFECT, reproduced from the live payload's own numbers. A verdict
    computed under a 42.0 bar must not be counted when the row publishes 36.0
    — and it must not silently vanish either."""
    s = _mum()
    b = _B(s)
    s.RSI_MAX = 36.0
    b.last_rsi = {"A": 37.1, "B": 40.0}      # nothing below the CURRENT bar
    b.last_uptrend = {"A": False, "B": False}
    b.last_enter = {"A": True, "B": False}
    b.last_enter_bar = {"A": 42.0}           # computed under the OLD bar
    scan = fam._census_extra(b)["scan"]
    assert scan["rsi_bar"] == 36.0 and scan["rsi_min"] == 37.1
    assert scan["both_terms_n"] == 0, (
        "a verdict computed under a different bar was counted at this one — "
        "the live defect, back")
    assert scan["both_terms_stale_n"] == 1, (
        "an unvouchable verdict must be SURFACED, not rounded to either "
        "answer: a widening is priced off this number")


def test_the_published_count_can_never_exceed_what_the_bar_allows():
    """The invariant the live row violated, stated directly: if no coin sits
    below `rsi_bar`, `both_terms_n` MUST be 0 — the conjunction cannot exceed
    the RSI term it contains."""
    s = _mum()
    for bar, rsis, enters, bars_at in (
            (36.0, {"A": 37.1}, {"A": True}, {"A": 42.0}),
            (36.0, {"A": 37.1}, {"A": True}, {}),          # unstamped
            (32.0, {"A": 33.0}, {"A": True}, {"A": 36.0}),
    ):
        b = _B(s)
        s.RSI_MAX = bar
        b.last_rsi, b.last_enter, b.last_enter_bar = rsis, enters, bars_at
        b.last_uptrend = {k: False for k in rsis}
        scan = fam._census_extra(b)["scan"]
        assert min(rsis.values()) >= bar, "fixture premise"
        assert scan["both_terms_n"] == 0, (bar, rsis, bars_at, scan)


def test_an_unstamped_verdict_degrades_to_stale_never_to_a_pass():
    """I8, on the exact term a widening is argued from. Restored pre-upgrade
    state carries no stamp; it must read UNKNOWN, never a fabricated pass."""
    s = _mum()
    b = _B(s)
    s.RSI_MAX = 36.0
    b.last_rsi = {"A": 20.0}                 # would genuinely pass the bar
    b.last_uptrend = {"A": False}
    b.last_enter = {"A": True}
    b.last_enter_bar = {}                    # no stamp at all
    scan = fam._census_extra(b)["scan"]
    assert scan["both_terms_n"] == 0 and scan["both_terms_stale_n"] == 1


def test_a_matching_bar_still_counts_so_the_gauge_is_not_merely_dead():
    """The positive control — a gauge that never counts anything is trivially
    consistent and useless (I3 applied to a gauge)."""
    s = _mum()
    b = _B(s)
    s.RSI_MAX = 36.0
    b.last_rsi = {"A": 20.0, "B": 50.0}
    b.last_uptrend = {"A": False, "B": False}
    b.last_enter = {"A": True, "B": False}
    b.last_enter_bar = {"A": 36.0, "B": 36.0}
    scan = fam._census_extra(b)["scan"]
    assert scan["both_terms_n"] == 1, scan
    assert "both_terms_stale_n" not in scan, "nothing was stale"


def test_both_arms_actually_WRITE_the_bar_stamp():
    """(vh): a fix verified in one file and shipped without asking which arm
    executes it reaches the shadow and not the real money. 👩 mum's LIVE row
    runs `lighter_avo_live_bot`.

    ON THE AST, not a substring. The first version of this test grepped the
    source for "last_enter_bar" and a mutation that DELETED the write from the
    live scan loop SURVIVED it — the name still appears in the init, the
    persistence dict and the census call. That is the fleet's own standing
    rule ("a page-wide substring scan is not a structural claim") reproduced
    inside the guard written to enforce it. A write is a Subscript in Store
    context; nothing else counts.
    """
    import ast
    import pathlib
    for mod, who in ((fam, "family"), (live, "live")):
        tree = ast.parse(pathlib.Path(mod.__file__).read_text())
        writes = [
            n for n in ast.walk(tree)
            if isinstance(n, ast.Subscript)
            and isinstance(n.ctx, ast.Store)
            and (getattr(n.value, "id", None) == "last_enter_bar"
                 or getattr(n.value, "attr", None) == "last_enter_bar")
        ]
        assert writes, (
            f"{who} arm never WRITES last_enter_bar — the stamp the census "
            f"counts against is never set, so every verdict reads stale")


# --- 2 · avo's BB dip gauge ------------------------------------------------

def test_the_bb_gauge_reports_the_binding_term():
    """`bb_dist_pct` is 100*(c/bb_lo-1): the conjunct PASSES below zero.

    The 0.0 cell is the one that matters and is why this fixture carries it:
    the shipped rule is `c[i] < bb_lo` — STRICT — so a close sitting exactly
    ON the band does NOT enter. A `<= 0` count would overstate the supply of
    the term a widening is argued from, and a mutation to `<=` survived the
    first version of this test because no coin sat on the boundary.
    """
    b = _B(_mum())
    b.last_bb = {"A": -1.5, "B": 0.0, "C": 0.4, "D": 3.0}
    scan = fam._census_extra(b)["scan"]
    assert scan["bb_min"] == -1.5, "the closest coin to entry"
    assert scan["bb_read"] == 4
    assert scan["bb_below_n"] == 1, (
        "only A is strictly below the band; B sits exactly ON it and the "
        "shipped comparison is strict")


def test_bb_is_absent_never_zero_when_nothing_was_read():
    """The (st) `rsi_min: 0.0` trap: a fabricated 0.0 reads as a coin sitting
    exactly ON the band — the loudest possible signal from no data (I8)."""
    b = _B(_mum())
    b.last_bb = {}
    scan = fam._census_extra(b)["scan"]
    for k in ("bb_min", "bb_med", "bb_read", "bb_below_n"):
        assert k not in scan, k


def test_the_live_arm_publishes_the_bb_gauge_too():
    """avo's real money runs the live host, so the gauge must exist there."""
    scan = live.scan_census(
        {}, {}, 42.0, ["A", "B"], [], None, None, None, None, 0.0,
        strategy=None, bb={"A": -2.0, "B": 1.0})
    assert scan["bb_min"] == -2.0 and scan["bb_below_n"] == 1, scan


def test_the_live_arm_counts_both_terms_at_the_published_bar():
    """The live half of the defect, driven through the shipped signature."""
    s = _mum()
    s.RSI_MAX = 36.0
    scan = live.scan_census(
        {}, {"A": 37.1}, 36.0, ["A"], [], None, None, None, None, 0.0,
        strategy=s, uptrend={"A": False}, enter={"A": True},
        enter_bar={"A": 42.0})
    assert scan["both_terms_n"] == 0 and scan["both_terms_stale_n"] == 1, scan


def test_the_new_gauges_survive_a_restart_on_the_live_arm():
    """Persisted AND restored, beside the maps they qualify.

    A mutation that dropped `last_enter_bar` from the persist dict survived
    the first round of this file. It is not dangerous — an unstamped verdict
    degrades to stale, which is the safe direction — but it would blank
    `both_terms_n` after every deploy until each coin's next candle, and (vm)
    already recorded why that is the WORSE failure on a book whose loop skips
    `signals()` between candles: "blank-most-of-the-time" is precisely the
    ambiguity this whole wave exists to remove.
    """
    import ast
    import pathlib
    src = (pathlib.Path(live.__file__)).read_text()
    tree = ast.parse(src)

    persisted = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        keys = {k.value for k in node.keys
                if isinstance(k, ast.Constant) and isinstance(k.value, str)}
        if "last_rsi" in keys and "scan_verdict" in keys:
            persisted |= keys
    assert {"last_enter_bar", "last_bb"} <= persisted, (
        "a new census map is not persisted beside `last_rsi` — a deploy would "
        f"blank it until the next candle. persisted={sorted(persisted)}")

    restored = {
        ast.unparse(n.args[0])
        for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and ast.unparse(n.func).endswith("state.get")
        and n.args and isinstance(n.args[0], ast.Constant)
    }
    for key in ("'last_enter_bar'", "'last_bb'"):
        assert key in restored, f"{key} is persisted but never restored"


def test_the_gauges_never_break_the_live_loop():
    """A census must never raise into a real-money trading loop."""
    s = _mum()
    scan = live.scan_census(
        {}, {"A": 37.1}, 36.0, ["A"], [], None, None, None, None, 0.0,
        strategy=s, uptrend={"A": False}, enter={"A": True},
        enter_bar="junk", bb="junk")
    assert isinstance(scan, dict)
