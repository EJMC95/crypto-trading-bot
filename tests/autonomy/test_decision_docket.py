"""[2026-08-06 (ld)] THE DECISION DOCKET — I17's overdue keep-or-retire calls.

WHY IT EXISTS. `(ks)` made the fleet's future computable per book, and nothing
carried a verdict to a DECISION. Measured on the live payload 6-Aug: **14 of 22
books** sat in a state I17 says must be decided (9 `unreachable`, 5
`undecidable`) while `OPERATOR_QUEUE.md` — hand-maintained — carried three of
them. A book could read "unreachable at trajectory" for weeks and never reach
the operator. That is the `(gk)` shape: the rule that governs real money ran
only when a human remembered it.

THE DESIGN CONSTRAINTS THESE TESTS PIN:
  * a verdict can flip on ONE trade, so a single reading is noise — the book
    must hold a stuck verdict for DOCKET_DAYS;
  * the clock RESETS when the verdict changes (two spells are not one spell);
  * a newborn book must NOT dock for being newborn (I7 — a trigger satisfied
    structurally is not a measurement);
  * an unreadable prior must fail toward SILENCE, never toward "the whole
    fleet is overdue" ((gl): a detector that cries wolf is ignored).
"""
import ast
import inspect
import math
import sys
import textwrap
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import golive_readiness as G  # noqa: E402


def iso(dt):
    return dt.isoformat(timespec="seconds")


T0 = datetime(2026, 8, 6, 9, 0, tzinfo=timezone.utc)


def book(verdict, n=50, mean=-0.2, t=-2.0, era_days=60.0, raw_days=None):
    return {"hz": {"verdict": verdict, "why": f"{verdict} at trajectory",
                   "raw_days": raw_days},
            "era_days": era_days, "n": n, "mean_pct": mean, "t": t}


class TestTheClock:
    def test_a_first_sighting_does_not_docket(self):
        d, seen = G.decision_docket({"a": book("unreachable")}, {}, iso(T0))
        assert d == []
        assert seen["a"]["reason"] == "unreachable"
        assert seen["a"]["since"] == iso(T0)

    def test_it_dockets_once_held_long_enough(self):
        start = iso(T0)
        seen = {"a": {"reason": "unreachable", "since": start}}
        later = iso(T0 + timedelta(days=G.DOCKET_DAYS))
        d, _ = G.decision_docket({"a": book("unreachable")}, seen, later)
        assert len(d) == 1
        assert d[0]["book"] == "a"
        assert d[0]["days_held"] == pytest.approx(G.DOCKET_DAYS, abs=0.05)
        assert "keep-or-retire" in d[0]["asks"]

    def test_it_stays_quiet_one_hour_short(self):
        seen = {"a": {"reason": "unreachable", "since": iso(T0)}}
        nearly = iso(T0 + timedelta(days=G.DOCKET_DAYS, hours=-1))
        d, _ = G.decision_docket({"a": book("unreachable")}, seen, nearly)
        assert d == []

    def test_the_clock_resets_when_the_verdict_changes(self):
        """unreachable -> undecidable is a NEW spell: the second is not
        evidence about the first."""
        old = iso(T0 - timedelta(days=30))
        seen = {"a": {"reason": "unreachable", "since": old}}
        d, new_seen = G.decision_docket({"a": book("undecidable")}, seen,
                                        iso(T0))
        assert d == [], "a changed verdict must restart the clock"
        assert new_seen["a"]["since"] == iso(T0)
        assert new_seen["a"]["reason"] == "undecidable"

    def test_recovery_drops_the_book_and_its_clock(self):
        old = iso(T0 - timedelta(days=30))
        seen = {"a": {"reason": "unreachable", "since": old}}
        d, new_seen = G.decision_docket({"a": book("on_track", mean=0.5, t=2.5)},
                                        seen, iso(T0))
        assert d == []
        assert "a" not in new_seen, "a recovered book keeps no clock"

    def test_a_long_stuck_book_reports_its_true_age(self):
        old = iso(T0 - timedelta(days=45))
        seen = {"a": {"reason": "unreachable", "since": old}}
        d, _ = G.decision_docket({"a": book("unreachable")}, seen, iso(T0))
        assert d[0]["days_held"] == pytest.approx(45.0, abs=0.05)


class TestWhoQualifies:
    @pytest.mark.parametrize("verdict", ["unreachable", "undecidable"])
    def test_the_two_i17_verdicts_qualify(self, verdict):
        stuck, reason = G._docket_stuck({"verdict": verdict})
        assert stuck and reason == verdict

    @pytest.mark.parametrize("verdict", ["ready", "on_track", "unprojectable",
                                         None, "", "nonsense"])
    def test_everything_else_does_not(self, verdict):
        stuck, _ = G._docket_stuck({"verdict": verdict}, era_days=999)
        assert not stuck

    def test_a_newborn_no_rate_book_does_not_docket(self):
        """🎸 Barnesy at n=8, days old. Docketing it would be the I7 error —
        every new book satisfies 'no rate' structurally."""
        stuck, _ = G._docket_stuck({"verdict": "no_rate"}, era_days=3.0)
        assert not stuck

    def test_a_no_rate_book_past_its_window_does_docket(self):
        """I17's own wording: still undecidable at the floor AFTER its
        window. 📊 equities-regime — 0 closes ever, alive for months."""
        stuck, reason = G._docket_stuck({"verdict": "no_rate"},
                                        era_days=G.GOLIVE_MIN_DAYS + 1)
        assert stuck and reason == "no_rate_past_window"

    def test_no_rate_at_exactly_the_window_qualifies(self):
        stuck, _ = G._docket_stuck({"verdict": "no_rate"},
                                   era_days=G.GOLIVE_MIN_DAYS)
        assert stuck

    @pytest.mark.parametrize("bad", [None, float("nan"), "60", float("inf")])
    def test_an_unusable_era_age_never_dockets_a_no_rate_book(self, bad):
        stuck, _ = G._docket_stuck({"verdict": "no_rate"}, era_days=bad)
        assert not stuck, "unknown age must not read as 'had its window'"


class TestFailSafe:
    def test_an_empty_prior_dockets_nobody(self):
        """The direction that matters: a lost prior must not declare the
        whole fleet overdue."""
        cur = {f"b{i}": book("unreachable") for i in range(14)}
        d, seen = G.decision_docket(cur, {}, iso(T0))
        assert d == []
        assert len(seen) == 14, "clocks still start, they just have not run"

    @pytest.mark.parametrize("junk", [None, [], "nope", 42])
    def test_a_junk_prior_is_treated_as_empty(self, junk):
        d, _ = G.decision_docket({"a": book("unreachable")}, junk, iso(T0))
        assert d == []

    @pytest.mark.parametrize("since", [None, "", "not-a-date", 12345])
    def test_an_unreadable_since_never_dockets(self, since):
        """An unparseable stamp must not become 'stuck forever' — nor 0 days,
        which would silently reset the clock on every run."""
        seen = {"a": {"reason": "unreachable", "since": since}}
        d, new = G.decision_docket({"a": book("unreachable")}, seen, iso(T0))
        assert d == []
        assert new["a"]["since"] == iso(T0) if not since else True

    def test_a_future_since_does_not_docket(self):
        seen = {"a": {"reason": "unreachable",
                      "since": iso(T0 + timedelta(days=5))}}
        d, _ = G.decision_docket({"a": book("unreachable")}, seen, iso(T0))
        assert d == []

    def test_a_missing_horizon_claims_nothing(self):
        d, seen = G.decision_docket({"a": {"hz": None, "era_days": 99}},
                                    {}, iso(T0))
        assert d == [] and seen == {}

    def test_days_between_refuses_junk(self):
        assert G._days_between("x", iso(T0)) is None
        assert G._days_between(iso(T0), "x") is None
        assert G._days_between(iso(T0 + timedelta(days=1)), iso(T0)) is None


class TestOrderingAndContent:
    def test_longest_stuck_comes_first(self):
        seen = {
            "old": {"reason": "unreachable", "since": iso(T0 - timedelta(days=40))},
            "new": {"reason": "unreachable", "since": iso(T0 - timedelta(days=8))},
        }
        cur = {"old": book("unreachable"), "new": book("unreachable")}
        d, _ = G.decision_docket(cur, seen, iso(T0))
        assert [x["book"] for x in d] == ["old", "new"]

    def test_the_entry_names_the_numbers_the_decision_needs(self):
        seen = {"a": {"reason": "unreachable", "since": iso(T0 - timedelta(days=10))}}
        d, _ = G.decision_docket({"a": book("unreachable", n=280, mean=-0.106,
                                            t=-1.53)}, seen, iso(T0))
        e = d[0]
        assert e["n"] == 280 and e["mean_pct"] == -0.106 and e["t"] == -1.53
        assert e["since"] and e["reason"] == "unreachable"

    def test_it_is_reported_never_a_bar(self):
        """BAR_NAMES is the published contract; the docket must not join it,
        and grade() must not consult it."""
        assert "docket" not in " ".join(G.BAR_NAMES).lower()
        src = textwrap.dedent(inspect.getsource(G.grade))
        assert "docket" not in src, "grade() must not read the docket"


class TestTheBatchStampIsDisclosedAsAFloor:
    """[(lu)] THE INCIDENT, measured on the live payload 13-Aug.

    `golive-docket-seen` held 20 clocks and NINE of them carried the identical
    `since` — `2026-08-06T12:28:34Z`, the second the (lf) key split deployed.
    At `DOCKET_DAYS=7` they were 6.73d from maturing TOGETHER, so the docket's
    first ever firing would have been nine books at once, every entry dated to
    a day on which nothing happened to any of them.

    The books were genuinely stuck (all `unreachable`), so suppressing is
    wrong; we do not know when each became stuck, so inventing an onset is
    worse (I8). What we know is a LOWER BOUND, and that is what must be said.
    """

    def _batch(self, k, days):
        stamp = iso(T0 - timedelta(days=days))
        seen = {f"b{i}": {"reason": "unreachable", "since": stamp}
                for i in range(k)}
        cur = {f"b{i}": book("unreachable") for i in range(k)}
        return G.decision_docket(cur, seen, iso(T0))

    def test_a_shared_second_is_flagged_as_a_floor_not_an_onset(self):
        d, _ = self._batch(G.BATCH_STAMP_MIN, 10)
        assert d, "the batch must still docket — these books ARE stuck"
        for e in d:
            assert e["since_is_floor"] is True
            assert e["batch_n"] == G.BATCH_STAMP_MIN
            assert "AT LEAST" in e["why"], (
                "an install-time clock reported as an onset is an unknown "
                "reading as a verdict")

    def test_a_lone_clock_is_reported_as_an_onset(self):
        """The flag must DISCRIMINATE. If everything is a floor, the field
        carries no information and the real batch stops standing out."""
        seen = {"solo": {"reason": "unreachable",
                         "since": iso(T0 - timedelta(days=10))}}
        d, _ = G.decision_docket({"solo": book("unreachable")}, seen, iso(T0))
        assert d[0]["since_is_floor"] is False
        assert "batch_n" not in d[0]
        assert "AT LEAST" not in d[0]["why"]

    def test_below_the_threshold_is_not_a_batch(self):
        d, _ = self._batch(G.BATCH_STAMP_MIN - 1, 10)
        assert all(e["since_is_floor"] is False for e in d)

    def test_a_batch_matures_together_and_every_member_is_flagged(self):
        """The whole batch crosses in one publish — that simultaneity IS the
        symptom — and no member may slip through unflagged.

        Recorded honestly: an earlier version of this test claimed the count
        had to be taken over `seen` rather than the matured `docket`, and a
        mutation swapping them SURVIVED. Books sharing a `since` to the second
        share `held`, so they mature together and the two bases agree. The
        real property is the one asserted here.
        """
        stamp = iso(T0 - timedelta(days=10))
        others = {f"y{i}": {"reason": "unreachable", "since": stamp}
                  for i in range(G.BATCH_STAMP_MIN)}
        solo = {"solo": {"reason": "unreachable",
                         "since": iso(T0 - timedelta(days=9))}}
        seen = {**others, **solo}
        cur = {k: book("unreachable") for k in seen}
        d, _ = G.decision_docket(cur, seen, iso(T0))
        assert len(d) == G.BATCH_STAMP_MIN + 1, "all of them matured"
        flagged = {e["book"] for e in d if e["since_is_floor"]}
        assert flagged == set(others), (
            "every batch member is flagged and the lone book is not — "
            "partial flagging would leave a wrong date in the docket")

    def test_the_live_13aug_batch_would_have_been_disclosed(self):
        """The incident itself, as a regression fixture: nine books sharing
        `2026-08-06T12:28:34Z`, read at the moment they crossed 7 days."""
        stamp = "2026-08-06T12:28:34+00:00"
        names = ["crypto-breakout-4h-lshadow", "freqtrade-dad-lshadow",
                 "lighter-perp-sniper-lshadow", "perps-funding-spread-lshadow",
                 "pm-abbott-lshadow", "pm-gillard-lshadow",
                 "pm-morrison-lshadow", "pm-rudd-lshadow",
                 "pm-turnbull-lshadow"]
        seen = {n: {"reason": "unreachable", "since": stamp} for n in names}
        cur = {n: book("unreachable") for n in names}
        d, _ = G.decision_docket(cur, seen, "2026-08-13T12:28:34+00:00")
        assert len(d) == 9, "all nine cross in the same publish"
        assert all(e["since_is_floor"] and e["batch_n"] == 9 for e in d)
        assert all("AT LEAST" in e["why"] for e in d)


class TestTheMeasuredFleet:
    """The 6-Aug live reading, replayed: 14 of 22 books stuck."""

    LIVE = {  # (verdict, n, mean_pct, t) off bus.json golive_readiness
        "pm-abbott-lshadow": ("unreachable", 80, -0.232, -2.15),
        "pm-gillard-lshadow": ("unreachable", 280, -0.106, -1.53),
        "pm-rudd-lshadow": ("unreachable", 94, -0.116, -0.95),
        "pm-morrison-lshadow": ("unreachable", 22, -0.301, -0.54),
        "crypto-intraday-15m-lshadow": ("unreachable", 51, -0.095, -0.40),
        "crypto-breakout-4h-lshadow": ("unreachable", 7, -0.892, -2.06),
        "freqtrade-dad-lshadow": ("unreachable", 7, -2.940, -2.36),
        "lighter-perp-sniper-lshadow": ("unreachable", 14, -0.204, -0.24),
        "perps-funding-spread-lshadow": ("unreachable", 70, -2.307, -2.00),
        "perps-funding-lighter-lshadow": ("undecidable", 85, 0.074, 0.34),
        "freqtrade-georgia-lshadow": ("undecidable", 79, 0.043, 0.32),
        "pm-turnbull-lshadow": ("undecidable", 20, 0.022, 0.07),
        "pm-albanese-lshadow": ("undecidable", 21, 0.406, 0.52),
        "lighter-ticket-taker-lshadow": ("undecidable", 24, 0.445, 0.44),
        # NOT stuck — the fleet's only on-track book, and a newborn
        "perps-funding-lighter-lighter": ("on_track", 44, 0.219, 1.31),
        "band-barnes-lshadow": ("no_rate", 8, None, None),
    }

    def _cur(self):
        out = {}
        for b, (v, n, m, t) in self.LIVE.items():
            era = 3.0 if b == "band-barnes-lshadow" else 60.0
            out[b] = {"hz": {"verdict": v, "why": v}, "era_days": era,
                      "n": n, "mean_pct": m, "t": t}
        return out

    def test_first_run_dockets_nobody_but_clocks_everyone_stuck(self):
        d, seen = G.decision_docket(self._cur(), {}, iso(T0))
        assert d == []
        assert len(seen) == 14, sorted(seen)
        assert "perps-funding-lighter-lighter" not in seen
        assert "band-barnes-lshadow" not in seen, \
            "the newborn must not be clocked for being newborn"

    def test_a_week_later_all_fourteen_are_overdue(self):
        _, seen = G.decision_docket(self._cur(), {}, iso(T0))
        later = iso(T0 + timedelta(days=G.DOCKET_DAYS))
        d, _ = G.decision_docket(self._cur(), seen, later)
        assert len(d) == 14
        # gillard carries the fleet's largest stuck sample — the operator
        # should see the numbers, not a count
        g = next(x for x in d if x["book"] == "pm-gillard-lshadow")
        assert g["n"] == 280 and g["t"] == -1.53

    def test_the_parliament_is_six_of_them(self):
        _, seen = G.decision_docket(self._cur(), {}, iso(T0))
        d, _ = G.decision_docket(self._cur(), seen,
                                 iso(T0 + timedelta(days=G.DOCKET_DAYS)))
        pms = [x for x in d if x["book"].startswith("pm-")]
        assert len(pms) == 6, [x["book"] for x in d]


class TestItIsActuallyWired:
    def test_every_path_that_publishes_a_book_also_feeds_the_docket(self):
        """[(lf)] THIS TEST USED TO PIN THE BUG IN PLACE.

        It read `src.count("_docket_now[bot]") == 2` — a substring count that
        (a) asserted exactly TWO sources were correct, so adding the missing
        THIRD would have REDDENED the build, and (b) could never have matched
        the roster sweep anyway, which binds `_b` rather than `bot`. Meanwhile
        its own docstring claimed 📊 equities-regime was covered, and the live
        payload showed all 14 clocks coming from the graded path with the two
        zero-ledger books absent.

        The real invariant is a RELATIONSHIP: every path that can put a book
        into the payload must also offer it to the docket. Asserted over the
        AST by comparing the two target sets, so a fourth path cannot arrive
        quietly and a third does not have to fight the test.
        """
        src = textwrap.dedent(inspect.getsource(G.main))
        tree = ast.parse(src)

        def subscript_writers(name):
            out = set()
            for n in ast.walk(tree):
                if not isinstance(n, ast.Assign):
                    continue
                for t in n.targets:
                    if (isinstance(t, ast.Subscript)
                            and isinstance(t.value, ast.Name)
                            and t.value.id == name
                            and isinstance(t.slice, ast.Name)):
                        out.add(t.slice.id)
            return out

        pub = subscript_writers("payload_books") | subscript_writers("payload_floor")
        dock = subscript_writers("_docket_now")
        assert pub, "no publish paths found — the AST shape changed"
        assert pub <= dock, (
            f"these publish paths do not feed the docket: {sorted(pub - dock)} "
            f"(docket fed from {sorted(dock)}) — a book that reaches the "
            f"payload but not the docket is invisible to I17 forever")

    def test_the_roster_zero_ledger_books_can_actually_docket(self):
        """The motivating case, end to end. 📊 equities-regime has NO era, so
        the no_rate arm's `era_days >= 30` can never fire for it; without its
        own arm it was permanently un-docketable."""
        now = FI_ISO = iso(T0)
        cur = {"equities-regime-lshadow": {
            "hz": {"verdict": "no_rate", "why": "no closes ever"},
            "era_days": None, "roster_zero_ledger": True,
            "n": 0, "mean_pct": None, "t": None}}
        d, seen = G.decision_docket(cur, {}, now)
        assert seen["equities-regime-lshadow"]["reason"] == "zero_ledger"
        later = iso(T0 + timedelta(days=G.DOCKET_DAYS))
        d2, _ = G.decision_docket(cur, seen, later)
        assert len(d2) == 1 and d2[0]["book"] == "equities-regime-lshadow"

    def test_a_zero_ledger_flag_is_required_not_inferred(self):
        """A book with no era and a no_rate verdict but NOT from the roster
        (e.g. a newborn) must still stay quiet."""
        stuck, _ = G._docket_stuck({"verdict": "no_rate"}, era_days=None,
                                   roster_zero_ledger=False)
        assert not stuck

    def test_main_calls_decision_docket_and_publishes_it(self):
        src = textwrap.dedent(inspect.getsource(G.main))
        tree = ast.parse(src)
        called = {n.func.id for n in ast.walk(tree)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        assert "decision_docket" in called
        assert '"decision_docket": _docket' in src
        assert '"docket_seen": _seen' in src

    def test_the_prior_seen_map_is_actually_PASSED(self):
        """STRUCTURAL, and it earned its place.

        The first cut of the test above asserted only that
        `decision_docket(...)` is CALLED, and a mutation that replaced the
        prior argument with a literal `None` stayed GREEN — every offline
        test builds its own prior and passes it directly, so nothing noticed
        that main() had stopped reading the persisted one. With that mutation
        live the clock can never accumulate: every run is a first sighting
        and the docket is empty FOREVER, which is byte-identical to
        "no book is overdue". So the claim is made about the CALL SITE'S
        ARGUMENT, not the call.
        """
        src = textwrap.dedent(inspect.getsource(G.main))
        calls = [n for n in ast.walk(ast.parse(src))
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                 and n.func.id == "decision_docket"]
        assert calls, "main() no longer calls decision_docket"
        for c in calls:
            assert len(c.args) >= 2, ast.dump(c)
            prior = c.args[1]
            assert not isinstance(prior, ast.Constant), (
                "the prior seen-map must come from the persisted payload — a "
                "literal makes the clock unable to accumulate, and an empty "
                "docket then reads exactly like 'nothing is overdue'")
            # and it must actually reach into a loaded state object, not a
            # freshly-built dict ([(lf)]: the clocks now live in their own key,
            # so this reads `(_prior_seen or {}).get("seen")`)
            names = {n.id for n in ast.walk(prior) if isinstance(n, ast.Name)}
            assert any("prior" in n for n in names), (
                f"the prior must come from the LOADED state; got {ast.dump(prior)}")

    def test_the_clocks_are_written_only_on_a_successful_read(self):
        """[(lf)] The defect this split removed: `save_state` replaces a
        payload wholesale, so while the seen-map rode inside the grade payload
        a single unreadable prior wrote `{}` over every clock. Now the clocks
        have their own key and are persisted ONLY when the read succeeded."""
        src = textwrap.dedent(inspect.getsource(G.main))
        tree = ast.parse(src)
        writes = [n for n in ast.walk(tree)
                  if isinstance(n, ast.Call)
                  and isinstance(n.func, ast.Attribute)
                  and n.func.attr == "save_state"
                  and any(isinstance(a, ast.Name) and a.id == "DOCKET_SEEN_KEY"
                          for a in n.args)]
        assert writes, "the clocks must be persisted to their own key"
        # ...and that write must sit under a guard, not run unconditionally
        guarded = [n for n in ast.walk(tree) if isinstance(n, ast.If)
                   and any(w in ast.walk(n) for w in writes)]
        assert guarded, "the clock write must be guarded by the read result"
        assert any("_seen_ok" in ast.dump(g.test) for g in guarded), \
            "the guard must be the read-succeeded flag"

    def test_the_prior_read_is_checked(self):
        """(jz) seed class: a FAILED read must not look like 'no prior'.

        STRUCTURAL — the substring version of this test passed against DEAD
        CODE. Replacing the `hasattr(...)` guard with `False` leaves the
        checked call sitting unreachable in the branch body, the string still
        present, and every consumer silently back on the unchecked read. So
        the assertion is about the GUARD, not the presence of a name.
        """
        src = textwrap.dedent(inspect.getsource(G.main))
        # the GUARD itself must name the checked API — an `if False:` (or any
        # other constant) leaves the checked call unreachable while the name
        # still appears in the source
        guards = [n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.If)
                  and "load_state_checked" in ast.dump(n.test)]
        assert guards, (
            "no reachable guard selects the checked read — a failed prior "
            "read then looks exactly like 'no prior', resets every clock, "
            "and the docket is silently empty forever ((jz) seed class)")
        for node in guards:
            assert not isinstance(node.test, ast.Constant)

    def test_the_era_age_is_used_not_the_close_span(self):
        """(lb) established that s['days'] is the close SPAN and cannot
        advance during a stall — it must never answer 'had its window?'."""
        src = textwrap.dedent(inspect.getsource(G.main))
        assert '"era_days": _era_age_d(' in src
        assert '"era_days": s' not in src
