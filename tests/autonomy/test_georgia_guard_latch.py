"""[2026-08-27 (vn)] THE LOCKOUT MUST RUN FOR `stop` BARS, NOT FOR AS LONG AS
THE CLOSES THAT ARMED IT SIT IN THE LOOKBACK.

Eamon: *"unlock georgia"* / *"keep her at 5 bars"*. Measuring what "5 bars"
would have bought turned up the reason it would have bought nothing: the live
arm's `entries_lock` had NO LATCH.

The family `Book` this re-expresses checks its stored `guard_until` FIRST and
returns without re-evaluating, so a lockout stands for exactly `stop` bars.
The live arm recomputed `t_now + stop * tf_s` on EVERY loop while the trigger
held, and the entry gate is `t0 >= locked_until` — so the lock ran for as long
as `trades` stops sat inside the `lookback` window. On 🔮 georgia's 15m book
that is a configured 3h against an actual **12h**, on real money, with the
parameter meant to control it doing nothing at all.

Two arms re-expressing ONE protection and disagreeing about how long it runs
is `(vh)`'s class at a rail rather than at a gauge.
"""
import pathlib
import sys

_HERE = pathlib.Path(__file__).resolve()
sys.path.insert(0, str(_HERE.parents[2]))
sys.path.insert(0, str(_HERE.parent))

import lighter_family_bot as fam  # noqa: E402
# ONE owner for "load the live host AS a given book". The first draft of this
# file called `os.environ.setdefault("FAMILY_LIVE_BOOK", ...)` at import and so
# left the whole pytest process running as georgia — four unrelated tests
# (mum's variant boot, avo's clip arm, the telemetry cadence, the module
# selftest) failed downstream. `test_variant_host.loaded` already saves and
# restores the environment and reloads on the way out; its own docstring
# records the identical mistake being made once before. Importing it keeps
# that a single rule instead of a second copy free to disagree.
from test_variant_host import loaded  # noqa: E402


def _closes(n, t0, tf_s, stop=True):
    """n stopped closes, one per bar, ending at t0."""
    return [{"ts": t0 - i * tf_s, "pnl": -1.0, "pct": -0.05, "stop": stop,
             "pair": f"C{i}"} for i in range(n)]


def test_georgia_is_configured_at_five_bars():
    """The operator's number, on the carrier that runs her."""
    sg = fam.DayTraderGated.protections["slguard"]
    assert sg["stop"] == 5, (
        f"georgia's slguard stop is {sg['stop']} bars, not 5 — Eamon's call "
        "27-Aug. It is env-tunable (GEORGIA_SLGUARD_STOP_BARS) so the next "
        "move needs no deploy.")
    # ...and the bar count only means anything because the lock latches.
    assert sg["lookback"] > sg["stop"], (
        "a lookback at or below the stop makes the distinction untestable — "
        "the whole defect was the lock running to the LOOKBACK")


def test_a_running_lockout_is_reported_and_never_re_evaluated():
    """THE LATCH. While a lockout runs, the triggers must not be re-read: that
    is what let it extend itself for as long as the arming closes stayed in
    the window."""
    with loaded("freqtrade-georgia") as m:
        t0 = 1_700_000_000.0
        tf_s = m._interval_ms(m.S.tf) / 1000.0
        stop_bars = m.S.protections["slguard"]["stop"]
        armed_at = t0
        until = armed_at + stop_bars * tf_s

        # the trigger is STILL satisfied (3 fresh stops) — and the latch must win
        still_triggering = _closes(3, t0, tf_s)
        got_until, got_cause = m.entries_lock(
            still_triggering, t0 + tf_s, baseline=250.0,
            latch=(until, "slguard"))
        assert got_until == until, (
            "the lockout moved while it was running — it re-armed off the same "
            "closes, which is exactly the 12h-instead-of-3h defect")
        assert got_cause == "slguard", "the latched cause must survive"


def test_the_lockout_expires_after_stop_bars_even_if_the_stops_remain():
    """The release the operator actually asked for: 5 bars, then the triggers
    are re-read ONCE — not held for the 48-bar lookback."""
    with loaded("freqtrade-georgia") as m:
        t0 = 1_700_000_000.0
        tf_s = m._interval_ms(m.S.tf) / 1000.0
        sg = m.S.protections["slguard"]
        stop_bars, lookback = sg["stop"], sg["lookback"]

        # stops old enough to have left a `stop`-bar lockout but still INSIDE the
        # lookback — the exact window where the old code kept her shut.
        aged = stop_bars + 2
        assert aged < lookback, "fixture must sit inside the lookback"
        t_now = t0 + aged * tf_s
        closed = _closes(3, t0, tf_s)
        expired = (t0 + stop_bars * tf_s, "slguard")

        until, cause = m.entries_lock(closed, t_now, baseline=250.0, latch=expired)
        # the latch has expired, so the triggers ARE re-read — and they still fire,
        # which is correct — but the new release is `stop` bars from NOW, not from
        # whenever the closes age out of the lookback.
        assert until <= t_now + stop_bars * tf_s + 1, (
            f"a re-armed lockout runs to {until - t_now:.0f}s, longer than "
            f"{stop_bars} bars ({stop_bars * tf_s:.0f}s)")
        assert cause == "slguard"


def test_a_clean_book_is_not_locked_and_an_expired_latch_never_relocks():
    with loaded("freqtrade-georgia") as m:
        t0 = 1_700_000_000.0
        tf_s = m._interval_ms(m.S.tf) / 1000.0
        # no stops at all
        until, cause = m.entries_lock(
            [{"ts": t0, "pnl": 1.0, "pct": 0.01, "stop": False, "pair": "A"}],
            t0, baseline=250.0, latch=(t0 - 3600.0, "slguard"))
        assert until == 0.0 and cause is None, (
            "an EXPIRED latch must not keep a clean book shut — fail toward "
            "trading, since the stop, the daily halt and the kill switch are all "
            "still senior and untouched")


def test_a_junk_latch_degrades_to_evaluating_the_rule():
    """Fail-safe: state is a JSON round-trip. An unreadable latch must fall
    through to the real triggers, never lock (or unlock) on garbage."""
    with loaded("freqtrade-georgia") as m:
        t0 = 1_700_000_000.0
        tf_s = m._interval_ms(m.S.tf) / 1000.0
        for junk in (("nonsense", "slguard"), (None, None), (), "latch"):
            until, cause = m.entries_lock(_closes(3, t0, tf_s), t0,
                                          baseline=250.0, latch=junk)
            assert until > t0 and cause == "slguard", (
                f"junk latch {junk!r} did not fall through to the rule")


def test_the_latch_is_persisted_and_restored_like_the_familys_guard_until():
    """A redeploy must neither reset a running lockout nor resurrect an
    expired one — the [[lighter-flatten-silent-halt-redeploy-incident]] lesson
    pointing both ways."""
    import ast
    src = (pathlib.Path(__file__).resolve().parents[2]
           / "lighter_avo_live_bot.py").read_text()
    tree = ast.parse(src)

    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "_persist")
    persisted = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Dict):
            persisted |= {k.value for k in node.keys
                          if isinstance(k, ast.Constant)
                          and isinstance(k.value, str)}
    assert len(persisted) >= 5, "the _persist walk is broken"
    assert {"guard_until", "guard_cause"} <= persisted, (
        f"the lockout latch is not persisted (got {sorted(persisted)}) — a "
        "redeploy would clear a running real-money protection")

    restored = {ast.unparse(n.args[0]) for n in ast.walk(tree)
                if isinstance(n, ast.Call)
                and ast.unparse(n.func).endswith("state.get")
                and n.args and isinstance(n.args[0], ast.Constant)}
    for key in ("'guard_until'", "'guard_cause'"):
        assert key in restored, f"{key} is persisted but never restored"


def test_the_live_arm_and_the_family_agree_on_what_stop_means():
    """THE PROPERTY THE DEFECT BROKE. Both arms re-express one protection; a
    lockout must run for `stop` bars on BOTH, or the same book is protected
    differently depending on which file happens to run it."""
    with loaded("freqtrade-georgia") as m:
        tf_s = m._interval_ms(m.S.tf) / 1000.0
        sg = m.S.protections["slguard"]
        t0 = 1_700_000_000.0

        # family: drive the REAL `Book.entries_locked` against a stub `self`.
        # Constructing a Book builds a SafetyRails + ShadowBroker, which this test
        # neither needs nor should depend on — but the RULE must be the shipped
        # one, never a re-typed copy, so the unbound method is called directly.
        class _StubBook:
            pass

        b = _StubBook()
        b.bot_id = "freqtrade-georgia"
        b.s = fam.DayTraderGated("freqtrade-georgia", tf=m.S.tf, stoploss=-0.05,
                                 max_open=5, style="t", coins=["BTC"])
        b.guard_until = 0.0
        b.entries_locked = fam.Book.entries_locked.__get__(b, _StubBook)
        b.closed = _closes(3, t0, tf_s)
        assert b.entries_locked(t0, tf_s) is True
        fam_until = b.guard_until
        assert b.entries_locked(t0 + tf_s, tf_s) is True
        assert b.guard_until == fam_until, "the family latch moved — fixture is wrong"

        # live: same closes, same clock, same latch semantics
        live_until, _ = m.entries_lock(b.closed, t0, baseline=250.0, latch=None)
        assert abs((live_until - t0) - (fam_until - t0)) < 1.0, (
            f"the two arms disagree about the lockout length: live "
            f"{live_until - t0:.0f}s vs family {fam_until - t0:.0f}s")
        held, _ = m.entries_lock(b.closed, t0 + tf_s, baseline=250.0,
                                 latch=(live_until, "slguard"))
        assert held == live_until, "the live latch moved while the family's held"
