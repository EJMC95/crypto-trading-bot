"""[2026-08-06 (lf)] The judge's arm-drift sensor: the RULE and its WIRING.

WHY THIS FILE EXISTS. `(la)` scoped the row half of the drift check to the
bar's window and reported "5 mutations, each red" — but all five were inside
`_arm_drift_snapshot`. The fix's entire effect lives at the two CALL SITES in
`run_once`, and **reverting both to `since_ts=None` left the whole suite
GREEN**: no test in `tests/` referenced `_drift_snap`, `growth_window_start`,
`_rows_since` or `since_ts`. That is the `(hh)` dead-code class, in the same
commit whose fleet_immune half DID guard its wiring with an AST claim.

AND THE RULE ITSELF WAS WRONG. Scoping only changes the answer when an arm's
newest close falls outside the window. The GROWTH window is 2.5 days — wide
enough to straddle any deploy — so the scoped verdict was byte-identical to
the unscoped one, and production carried "ARMS ON DIFFERENT CODE" on five
consecutive samples AFTER `(la)` landed, holding a growth bar whose floors
were both met, while `bot_pnl` showed both containers on the same build.
`(lf)` replaces newest-vs-newest with **build-set disjointness**.
"""
import ast
import inspect
import textwrap

import pytest

import experiment_judge as J


L, S = J.LIVE_BOT, J.SHADOW_BOT
W0 = 1_700_000_000.0


def row(bot, build, at):
    return {"bot": bot, "close_ts": J.iso(at), "extra": {"build": build}}


class TestTheRule:
    def test_disjoint_sets_are_drift(self):
        rows = [row(L, "A", W0 + 10), row(S, "B", W0 + 20)]
        d = J._row_drift(rows)
        assert d and d["source"] == "rows-disjoint"

    def test_a_rolling_deploy_is_not_drift(self):
        """THE LIVE DEFECT. Both arms cross the same deploy; the slower arm's
        newest close is still the old build. Sets intersect => timing."""
        rows = [row(L, "A", W0 + 10), row(L, "B", W0 + 20),
                row(S, "A", W0 + 15), row(S, "B", W0 + 25),
                row(S, "C", W0 + 40)]
        assert J._row_drift(rows) is None

    def test_one_shared_build_is_enough_to_clear(self):
        rows = [row(L, "A", W0), row(S, "A", W0), row(S, "Z", W0 + 1)]
        assert J._row_drift(rows) is None

    @pytest.mark.parametrize("rows", [
        [],
        [row(L, "A", W0)],                                  # one arm only
        [row(L, "A", W0), {"bot": S, "extra": {}}],         # shadow unstamped
        [{"bot": L, "extra": {}}, {"bot": S, "extra": {}}],  # neither stamped
    ])
    def test_unknown_is_never_drift(self, rows):
        assert J._row_drift(rows) is None

    def test_the_live_6aug_shape_does_not_claim_drift(self):
        """Reconstructed from the real ledger: live {f27e,6ff8},
        shadow {f27e,6ff8,4f99}. This is what held the growth bar."""
        rows = ([row(L, "f27e50d805af", W0 + i) for i in range(5)]
                + [row(L, "6ff86f4d6b09", W0 + 10 + i) for i in range(4)]
                + [row(S, "f27e50d805af", W0 + i) for i in range(5)]
                + [row(S, "6ff86f4d6b09", W0 + 10 + i) for i in range(7)]
                + [row(S, "4f998e4eec4d", W0 + 30 + i) for i in range(3)])
        assert J._row_drift(rows) is None


class TestTheContainerHalfIsUntouched:
    def test_containers_on_two_builds_still_hold(self):
        rows = [row(L, "A", W0), row(S, "A", W0)]          # rows agree
        pnl = [{"bot": L, "extra": {"build": "x"}},
               {"bot": S, "extra": {"build": "y"}}]
        d = J._arm_drift_snapshot(rows, since_ts=W0, fetch=lambda: pnl)
        assert d == {"live": "x", "shadow": "y", "source": "bot_pnl-current"}

    def test_a_dark_fetch_claims_nothing(self):
        def boom():
            raise RuntimeError("db down")
        rows = [row(L, "A", W0), row(S, "A", W0)]
        assert J._arm_drift_snapshot(rows, since_ts=W0, fetch=boom) is None


class TestTheWiring:
    """The claim (la) never made: both call sites must actually scope."""

    @staticmethod
    def _calls():
        src = textwrap.dedent(inspect.getsource(J.run_once))
        return [n for n in ast.walk(ast.parse(src))
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id == "_arm_drift_snapshot"]

    def test_both_call_sites_exist(self):
        assert len(self._calls()) == 2, \
            "run_once must scope the drift snapshot on BOTH the growth and " \
            "serial paths"

    def test_every_call_site_passes_a_real_since_ts(self):
        """Reverting either to `since_ts=None` left the entire suite green."""
        for c in self._calls():
            kw = {k.arg: k.value for k in c.keywords}
            assert "since_ts" in kw, ast.dump(c)
            assert not isinstance(kw["since_ts"], ast.Constant), (
                "since_ts must be a computed window, not a literal — a literal "
                "None restores the whole-ledger comparison (la) set out to fix")

    def test_the_growth_call_site_uses_the_one_window_definition(self):
        """A second copy of `now - GROWTH_WINDOW_D*86400` at the call site
        would be a second rule ((hj))."""
        srcs = []
        for c in self._calls():
            kw = {k.arg: k.value for k in c.keywords}
            srcs.append(ast.dump(kw["since_ts"]))
        assert any("growth_window_start" in s for s in srcs), srcs

    def test_the_container_half_is_read_once_and_shared(self):
        src = textwrap.dedent(inspect.getsource(J.run_once))
        tree = ast.parse(src)
        cur = [n for n in ast.walk(tree)
               if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
               and n.func.id == "_current_drift"]
        assert len(cur) == 1, "one bot_pnl reading per cycle, not one per window"
        for c in self._calls():
            kw = {k.arg: k.value for k in c.keywords}
            assert "current" in kw, ast.dump(c)

    def test_the_row_half_goes_through_the_set_rule(self):
        """_arm_drift_snapshot must not fall back to the newest-vs-newest
        helper for LEDGER rows — that helper is correct for bot_pnl only."""
        src = textwrap.dedent(inspect.getsource(J._arm_drift_snapshot))
        tree = ast.parse(src)
        called = {n.func.id for n in ast.walk(tree)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        assert "_row_drift" in called
