"""💰 fleet_allocation — the organ that answers "where should the capital be?".

WHY IT EXISTS (2026-08-01): the fleet had a dozen organs answering "is this
book safe?" and none answering "where should the money go?". Every shadow book
carries $1,000 regardless of evidence, so the best-evidenced book and a book
with zero closed trades in twenty days are funded identically.

Measured on the live ledger the day it shipped: FUNDING 3 books / 212 closes /
net +$72.89 against DIRECTIONAL 18 books / 809 closes / net -$9.21.

The two failure classes these tests exist to prevent:
  * A RANKING THAT REWARDS LUCK — a big mean on a tiny sample out-claiming a
    modest, well-evidenced one. The lower bound exists precisely to stop that.
  * AN ORGAN THAT INVENTS AN OPINION — with no measured claim anywhere the
    output must be EXACTLY the flat allocation, not a plausible-looking split.
"""
import ast
import pathlib

import pytest

import fleet_allocation as alloc

ROOT = pathlib.Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.autonomy


class TestTheRankingRule:
    def test_the_bound_sits_below_the_mean(self):
        v = [0.03, 0.01, 0.02, 0.04] * 10
        lb = alloc.lower_bound(v)
        assert lb is not None and lb < sum(v) / len(v)

    def test_more_evidence_strengthens_the_claim(self):
        """The self-correcting property: same mean, more n, tighter bound."""
        few = alloc.lower_bound([0.03, 0.01, 0.02, 0.04] * 5)
        many = alloc.lower_bound([0.03, 0.01, 0.02, 0.04] * 50)
        assert many > few

    def test_luck_does_not_outrank_evidence(self):
        """THE assertion that makes the rule worth having: a 5% mean on n=5
        must not beat a 0.2% mean on n=80."""
        a = alloc.allocate({"lucky": [0.05, 0.04, 0.06, 0.05, 0.05],
                            "steady": [0.002, 0.001, 0.003, 0.002] * 20},
                           book_usd=1000.0)
        assert a["steady"]["target_usd"] > a["lucky"]["target_usd"]
        assert a["lucky"]["undecided"] is True

    @pytest.mark.parametrize("bad", [[], [0.01], [0.01] * 40])
    def test_no_opinion_is_None_never_zero(self, bad):
        """'no opinion' and 'measured zero' must not collapse into one number.
        The constant series is the trap: identical returns do not give exactly
        zero variance in floating point, so a naive `var <= 0` check lets a
        degenerate book out-claim every real one."""
        assert alloc.lower_bound(bad) is None


class TestItCannotInventOrOverspend:
    def test_total_capital_is_conserved(self):
        books = {"x": [0.01, 0.02, 0.0, 0.015] * 12,
                 "y": [-0.02, -0.01, -0.03, 0.0] * 12, "z": []}
        a = alloc.allocate(books, book_usd=1000.0)
        assert abs(sum(r["target_usd"] for r in a.values())
                   - 1000.0 * len(a)) < 0.05

    def test_no_claim_anywhere_gives_EXACTLY_the_flat_allocation(self):
        a = alloc.allocate({"p": [-0.02, -0.01, -0.03, 0.0] * 10,
                            "q": [-0.03, -0.02, -0.01, -0.04] * 10},
                           book_usd=1000.0)
        for r in a.values():
            assert abs(r["target_usd"] - 1000.0) < 0.05

    def test_every_book_keeps_a_probe_floor(self):
        """A book cannot earn evidence with no capital — starving an undecided
        book to zero is how a fleet stops learning."""
        a = alloc.allocate({"bad": [-0.06, -0.04, -0.05, -0.03] * 10,
                            "good": [0.03, 0.01, 0.02, 0.04] * 10},
                           book_usd=1000.0)
        assert a["bad"]["claim"] == 0.0
        assert a["bad"]["target_usd"] >= 1000.0 * alloc.PROBE_FLOOR
        assert a["good"]["target_usd"] > a["bad"]["target_usd"]

    def test_it_never_proposes_a_negative_allocation(self):
        a = alloc.allocate({f"b{i}": [-0.1, -0.2, -0.05, -0.15] * 10
                            for i in range(6)}, book_usd=1000.0)
        assert all(r["target_usd"] >= 0 for r in a.values())


class TestTheContract:
    def test_the_payload_declares_it_moves_nothing(self):
        """An allocation VIEW that could be read as an instruction is how a
        shadow book ends up funded by momentum."""
        p = alloc.build({"m": [0.01, 0.02, 0.0, 0.015] * 10})
        assert p["advisory"] is True
        assert p["moves_capital"] is False
        assert p["rule"] and p["ttl_sec"] > 0

    def test_it_writes_no_lever(self):
        import pathlib as _p
        src = (_p.Path(__file__).resolve().parents[2]
               / "fleet_allocation.py").read_text()
        for forbidden in ("write_levers", "get_lever", "fleet_tuning",
                          "market_open", "publish_paper_trade"):
            assert forbidden not in src, (
                f"{forbidden} in an ADVISORY organ — it must move no capital")

    def test_class_is_by_signal_not_name_prefix(self):
        assert alloc.book_class("perps-funding-carry-lshadow") == "funding"
        assert alloc.book_class("perps-funding-spread-lshadow") == "funding"
        assert alloc.book_class("crypto-trend-daily-lshadow") == "directional"
        assert alloc.book_class(None) == "directional", \
            "unknown must never claim the funding class"

    @pytest.mark.parametrize("junk", [{}, {"a": None}, {"a": [None, None]}])
    def test_junk_never_raises_inside_an_organ_loop(self, junk):
        alloc.build(junk)

    def test_it_ships_in_the_image_and_has_a_deploy_route(self):
        """A new module that is COPY'd but not on `paths:` is born dark — this
        repo's most repeated shipping defect."""
        import pathlib as _p
        root = _p.Path(__file__).resolve().parents[2]
        assert "fleet_allocation.py" in (root / "Dockerfile.freqtrade").read_text()
        wf = (root / ".github/workflows/railway-redeploy.yml").read_text()
        assert "- 'fleet_allocation.py'" in wf, "no push path -> never deploys"
        assert "fleet_allocation\\.py$" in wf, "not in the service grep"
        assert "fleet_allocation.py --publish" in (root / "run_all.sh").read_text()


def test_the_era_headline_counts_a_field_that_exists_by_then():
    """`n_with_era_claim` must be computed AFTER the era twins are filled.

    [2026-08-26] THE DEFECT. `build()` computes `by_class` — including
    `n_with_era_claim` — and the era twin is filled later, in `run_once`,
    because it needs the ledger rows and the era owner's import. `build` cannot
    know it, so it sets every `claim_era` to None first ((lx)). The counter
    therefore ran over a column that was None on every book by construction,
    and could only ever report ZERO whatever the data said.

    Measured live: `freqtrade-avo-maria-lighter` published
    `claim_era: 0.000174` — a real positive era-scoped claim — beside a
    headline reading `n_with_era_claim: 0`. The payload contradicted itself.

    Two halves pinned: the aggregator counts era claims when they are present,
    and `run_once` recomputes the headline after filling them.
    """
    # --- half one: the aggregator itself can count an era claim -------------
    books = {"a": [0.03, 0.01, 0.02, 0.04] * 5, "b": [-0.02, -0.01] * 10}
    rows = alloc.allocate(books, book_usd=1000.0)
    before = alloc.class_totals(rows, books)
    assert sum(c["n_with_era_claim"] for c in before.values()) == 0, \
        "fixture must start with no era claims, or it proves nothing"
    alloc.set_era_twin(rows["a"], 12, 0.004)
    after = alloc.class_totals(rows, books)
    assert sum(c["n_with_era_claim"] for c in after.values()) == 1, \
        "the aggregator does not see a filled era twin"

    # --- half two: run_once recomputes it AFTER the fill --------------------
    # Structural, because the ordering IS the defect — an aggregator that works
    # in isolation is exactly what shipped, and it still published zero.
    src = (ROOT / "fleet_allocation.py").read_text()
    tree = ast.parse(src)
    fn = [f for f in ast.walk(tree)
          if isinstance(f, ast.FunctionDef) and f.name == "run_once"][0]
    fill_line = None
    recompute_line = None
    for node in ast.walk(fn):
        if (isinstance(node, ast.Call) and getattr(node.func, "id", "")
                == "set_era_twin"):
            fill_line = max(fill_line or 0, node.lineno)
        if isinstance(node, ast.Assign):
            for t in node.targets:
                # NOTE the quote form: `ast.unparse` emits SINGLE quotes,
                # so matching on `["by_class"]` finds nothing and this fails
                # for the wrong reason. Match the KEY, not a spelling.
                if (isinstance(t, ast.Subscript)
                        and "by_class" in ast.unparse(t)):
                    recompute_line = max(recompute_line or 0, node.lineno)
    assert fill_line, "run_once no longer fills the era twin"
    assert recompute_line, (
        "run_once never recomputes by_class — the headline is whatever "
        "build() computed before any claim_era existed, i.e. always zero")
    assert recompute_line > fill_line, (
        f"by_class is recomputed at line {recompute_line} but the era twins "
        f"are filled at {fill_line} — the counter still precedes its data")


def test_the_gate_publishes_the_capital_it_withholds():
    """The era gate is not capital-conserving, and the payload must say so.

    [2026-08-26] `target_usd` is conserved BY CONSTRUCTION — the split never
    proposes spending more, only spending it differently. The era gate ((lx))
    is not: a book it declines is held at flat, and the surplus the tilt took
    from every OTHER book to fund that expansion is returned to nobody. So the
    two published halves of the allocation do not add up.

    `(oy)` published the gated outcome PER BOOK for exactly this reason and
    left the fleet-level number underived. Measured on the live payload the day
    this shipped: sum(target_usd) $19,999.96 vs $18,848.30 reachable —
    **$1,151.66, 5.8% of fleet capital**, with 3 books `expansion_gated` and 16
    sitting at 0.9279x flat to fund a bonus that was refused.

    Pinned in BOTH directions, because a number that is always positive is not
    a measurement: a gated book produces a withholding, and an ungated fleet
    produces exactly zero.
    """
    books = {"a": [0.03, 0.01, 0.02, 0.04] * 5, "b": [-0.02, -0.01] * 10,
             "c": [0.0005, -0.0005] * 10}
    rows = alloc.allocate(books, book_usd=1000.0)
    # `a` is the claimant, so the tilt puts it above flat.
    for b in rows:
        alloc.set_era_twin(rows[b], None, None)   # writes scale_effective too
    assert rows["a"]["expansion_gated"], (
        "fixture must produce a gated claimant, or it proves nothing: "
        f"{ {b: (rows[b]['target_usd'], rows[b]['scale_effective']) for b in rows} }")
    g = alloc.gate_totals(list(rows.values()))
    assert g["n_expansion_gated"] == 1, g
    assert g["n_unpriced"] == 0, g
    assert g["withheld_usd"] > 0, (
        "a declined expansion withholds real capital and the headline read "
        f"zero: {g}")
    # ...and it is exactly what the gate refused, not an approximation.
    refused = rows["a"]["target_usd"] - rows["a"]["current_usd"]
    assert abs(g["withheld_usd"] - refused) < 0.02, (g, refused)

    # THE OTHER DIRECTION: grant the era claim and the leak must vanish.
    alloc.set_era_twin(rows["a"], 12, 0.004)
    g2 = alloc.gate_totals(list(rows.values()))
    assert g2["n_expansion_gated"] == 0 and g2["withheld_usd"] == 0.0, (
        "with nothing gated the allocation closes exactly, and a headline that "
        f"still reports a leak is manufacturing one: {g2}")


def test_an_unpriceable_row_is_counted_not_swallowed():
    """A row whose effective scale cannot be computed falls back to its raw
    target — and says so. ((kw)/I4: a dark computation must never be
    byte-identical to a clean one.)"""
    junk = {"target_usd": 1500.0, "current_usd": None,
            "scale_effective": None, "expansion_gated": False}
    g = alloc.gate_totals([junk])
    assert g["n_unpriced"] == 1, g
    assert g["withheld_usd"] == 0.0 and g["target_effective_usd"] == 1500.0, (
        "an unpriceable row must fall back to its raw target rather than "
        f"reading as $1,500 withheld: {g}")


def test_the_fleet_gate_headline_is_computed_after_the_era_fill():
    """Same ordering constraint as `n_with_era_claim`, same reason.

    [2026-08-26] `scale_effective` and `expansion_gated` are written when
    `claim_era` becomes known. A fleet-level total computed before that fill
    would see every book ungated and report a leak of exactly zero — the (ua)
    defect in a second field, which is why it is pinned rather than assumed.
    """
    src = (ROOT / "fleet_allocation.py").read_text()
    fn = [f for f in ast.walk(ast.parse(src))
          if isinstance(f, ast.FunctionDef) and f.name == "run_once"][0]
    fill_line = gate_line = None
    for node in ast.walk(fn):
        if (isinstance(node, ast.Call)
                and getattr(node.func, "id", "") == "set_era_twin"):
            fill_line = max(fill_line or 0, node.lineno)
        if isinstance(node, ast.Assign):
            for t in node.targets:
                # `ast.unparse` emits SINGLE quotes — match the KEY, never a
                # spelling (the trap this file already walked into once).
                if isinstance(t, ast.Subscript) and "'gate'" in ast.unparse(t):
                    gate_line = min(gate_line or 10**9, node.lineno)
    assert fill_line, "run_once no longer fills the era twin"
    assert gate_line, (
        "run_once never publishes the fleet gate total — the leak the payload "
        "exists to make readable is underived again")
    assert gate_line > fill_line, (
        f"payload['gate'] is set at line {gate_line} but the era twins are "
        f"filled at {fill_line} — it would report a leak of zero always")


class TestTheEvidenceRecordIsPublished:
    """[2026-08-05 (kc)] The payload used to publish {n, claim, class,
    target_usd, current_usd, delta_usd, undecided} and nothing else, so two
    books failing for OPPOSITE reasons were byte-identical rows.

    Measured on the live ledger the day this shipped: pm-rudd (n=94, mean
    -0.116%/trade, bound straddling zero — "not enough sample to say") and
    pm-abbott (n=79, mean -0.224%, upper bound below zero — "measured loser")
    published the same row. I17's keep-or-retire call has opposite answers for
    those two and could not be made from the organ that exists to inform it.
    """

    def test_the_published_claim_is_reproducible_from_the_published_stats(self):
        r = alloc.allocate({"w": [0.02, 0.01, 0.03, -0.005] * 8},
                           book_usd=1000.0)["w"]
        assert r["mean_pct"] is not None and r["se_pct"] is not None
        # [2026-08-20] through the PUBLISHED `crit`, not a retyped constant.
        # The critical value varies with n now, so this test used to hold only
        # because the module happened to use the same number the test typed —
        # which is the second-rule shape it was written to forbid. Rebuilding
        # from the payload alone is the stronger claim, and it is the one a
        # reader with only /bus.json can actually check.
        assert r["crit"] is not None, "the payload must say what it judged at"
        assert abs(r["claim"] - max(0.0, r["mean_pct"]
                                    - r["crit"] * r["se_pct"])) < 1e-5, \
            ("mean_pct/se_pct/crit must describe the SAME sample the claim was "
             "ranked on — if they cannot rebuild it, they are a second rule")

    def test_the_critical_value_is_derived_from_the_sample_not_fixed(self):
        """The cliff's replacement: a thinner sample must be doubted MORE.

        With a constant z this was flat, and the only protection against a
        lucky 3-close book was a hard n>=20 cliff that also deleted every
        genuine claim below it (measured: three living books, and FIVE
        `claim_era: None`s including the fleet's top-ranked book).
        """
        thin = alloc.allocate({"a": [0.03, 0.01, 0.02, 0.04] * 3},
                              book_usd=1000.0)["a"]
        thick = alloc.allocate({"a": [0.03, 0.01, 0.02, 0.04] * 30},
                               book_usd=1000.0)["a"]
        assert thin["crit"] > thick["crit"], (thin["crit"], thick["crit"])
        assert thick["crit"] >= alloc.Z_LOWER, "the floor must still bind"

    def test_a_floored_claim_still_publishes_its_bound_and_its_distance(self):
        """`claim: 0.0` was byte-identical for 15 of 19 live books whose bounds
        ran from -0.02% to -0.64%. The ordering was computed and discarded one
        character before the payload."""
        r = alloc.allocate({"a": [0.02, -0.018, 0.021, -0.019, 0.001] * 6},
                           book_usd=1000.0)["a"]
        assert r["claim"] == 0.0
        assert r["bound_pct"] is not None and r["bound_pct"] < 0.0
        assert r["n_req_claim"] and r["n_req_claim"] > r["n"], \
            "a positive-mean book below the bar must say how far it has to go"
        lost = alloc.allocate({"a": [-0.02, -0.01, -0.03, 0.0] * 6},
                              book_usd=1000.0)["a"]
        assert lost["n_req_claim"] is None, \
            "more of a negative sample never reaches a claim — say so"

    def test_the_distance_to_a_claim_honours_the_luck_floor(self):
        """A book cannot hold a claim below MIN_N however good its arithmetic
        looks, so a smaller `n_req_claim` would be a lie about what it needs."""
        r = alloc.allocate({"a": [0.01, 0.02]}, book_usd=1000.0)["a"]
        assert r["n_req_claim"] == alloc.MIN_N, (r["n_req_claim"], alloc.MIN_N)

    def test_the_luck_floor_is_the_winners_docket_floor(self):
        """10, and it is doctrine (I21), not a tunable. The t critical value
        widens a thin interval but cannot repair a variance estimate built from
        three numbers — measured: a 3-close era sample at t=33 yields a bound of
        +2.97%/trade, which would outrank every living book in the fleet."""
        assert alloc.MIN_N >= 10, alloc.MIN_N
        streak = alloc.allocate({"a": [0.031, 0.030, 0.032]},
                                book_usd=1000.0)["a"]
        assert streak["claim"] == 0.0 and streak["undecided_why"] == "below-min-n"

    def test_no_opinion_reaches_the_payload_as_none_never_as_zero(self):
        """lower_bound's own rule — 'no opinion' and 'measured zero' must not
        collapse into the same number — carried through to the payload boundary
        instead of stopping one layer short of it."""
        flat = alloc.allocate({"f": [0.01] * 30}, book_usd=1000.0)["f"]
        assert flat["mean_pct"] is None and flat["se_pct"] is None
        assert flat["undecided_why"] == "no-bound"
        # ...while a MEASURED loser still publishes its measurement, because
        # that is the number the retire conversation needs.
        neg = alloc.allocate({"g": [-0.02, -0.01, -0.03, 0.0] * 8},
                             book_usd=1000.0)["g"]
        assert neg["claim"] == 0.0 and neg["undecided_why"] == "bound<=0"
        assert neg["mean_pct"] is not None and neg["mean_pct"] < 0

    def test_thin_and_losing_are_distinguishable(self):
        """The whole point: the two failure modes have OPPOSITE remedies."""
        a = alloc.allocate({"thin": [0.05, 0.04, 0.06, 0.05, 0.05],
                            "losing": [-0.02, -0.01, -0.03, 0.0] * 8},
                           book_usd=1000.0)
        assert a["thin"]["undecided_why"] == "below-min-n"
        assert a["losing"]["undecided_why"] == "bound<=0"
        assert a["thin"]["undecided_why"] != a["losing"]["undecided_why"], \
            "a payload that cannot tell 'no sample' from 'no edge' informs nothing"

    def test_a_claim_never_exceeds_its_own_sample_mean(self):
        """RED-LINES any future estimator — pooling, shrinkage, a rate
        multiplier — that would hand a book a claim its OWN sample cannot
        support. A lower bound that sits above the mean is not a lower bound.
        """
        for pcts in ([0.02, 0.01, 0.03, -0.005] * 8,
                     [0.002, 0.001, 0.003, 0.002] * 20,
                     [0.05, -0.01, 0.02, 0.04] * 10):
            r = alloc.allocate({"b": pcts}, book_usd=1000.0)["b"]
            if r["claim"] > 0:
                assert r["claim"] < r["mean_pct"], \
                    "a bound above its own mean is not a bound"


class TestEveryLivingBookReachesThePayload:
    """[2026-08-05 (kc)] I17: 'every living book keeps a 25% probe floor,
    because a book cannot earn evidence with no capital.'

    The I/O shell built its book set from LEDGER ROWS ONLY, so a book with ZERO
    closes never entered the payload and got no floor — the organ was silent
    about precisely the case the invariant was written for. Measured that day:
    band-barnes-lshadow (10 open / 0 closed), equities-regime-lshadow (5 open)
    and freqtrade-mum-lshadow (4 open) were all absent.

    The pre-existing test_every_book_keeps_a_probe_floor stayed GREEN through
    all of it, because it drives `allocate` with a fixture that always contains
    the book. That is the CLAUDE.md header caveat in one place: a green run
    verifies the enforcement EXISTS, not that it is CORRECT.
    """

    def _store(self, monkeypatch, pnl_rows, trades):
        import types
        fake = types.SimpleNamespace(
            fetch_bot_pnl=lambda: pnl_rows,
            fetch_paper_trades=lambda limit=8000: trades,
            save_state=lambda *a, **k: True,
            save_history=lambda *a, **k: True,
        )
        monkeypatch.setattr(alloc, "store", fake)
        return fake

    def _row(self, bot, opened=0, closed=0):
        from datetime import datetime, timezone
        return {"bot": bot, "updated_at": datetime.now(timezone.utc).isoformat(),
                "status": "online", "open_trades": opened,
                "closed_trades": closed, "extra": {}}

    def test_a_zero_close_living_book_gets_a_row_and_the_probe_floor(
            self, monkeypatch):
        self._store(monkeypatch,
                    [self._row("newbook-lshadow", opened=10, closed=0),
                     self._row("tradedbook-lshadow", opened=1, closed=40)],
                    [{"bot": "tradedbook-lshadow", "profit_ratio": p,
                      "profit_abs": 1.0, "open_ts": None, "close_ts": None,
                      "extra": {}}
                     for p in [0.01, 0.02, 0.0, 0.015] * 10])
        p = alloc.run_once(publish=False)
        assert "newbook-lshadow" in p["books"], \
            "a living book with zero closes must still reach the payload"
        r = p["books"]["newbook-lshadow"]
        assert r["n"] == 0
        assert r["target_usd"] >= p["book_usd"] * alloc.PROBE_FLOOR, \
            "I17's floor is not optional, and this is the case it is FOR"
        assert "newbook-lshadow" in p["zero_close_books"]

    def test_a_non_book_service_row_is_never_allocated_capital(
            self, monkeypatch):
        """A market-data publisher is not a book. It reports no trade counts,
        which is the semantic discriminator — not a name list, so a FUTURE
        service row is excluded the day it appears."""
        svc = self._row("some-context-service")
        svc["open_trades"] = svc["closed_trades"] = None
        self._store(monkeypatch, [svc, self._row("realbook-lshadow", 1, 5)],
                    [{"bot": "realbook-lshadow", "profit_ratio": 0.01,
                      "profit_abs": 1.0, "open_ts": None, "close_ts": None,
                      "extra": {}}])
        p = alloc.run_once(publish=False)
        assert "some-context-service" not in p["books"], \
            "allocating capital to a data publisher is a category error"
        assert "realbook-lshadow" in p["books"]

    def test_a_retired_book_stays_out_even_with_a_fresh_row(self, monkeypatch):
        from cleanup_legacy_bots import LEGACY_BOTS
        dead = sorted(LEGACY_BOTS)[0]
        self._store(monkeypatch,
                    [self._row(dead, opened=3, closed=0),
                     self._row("realbook-lshadow", 1, 5)],
                    [{"bot": "realbook-lshadow", "profit_ratio": 0.01,
                      "profit_abs": 1.0, "open_ts": None, "close_ts": None,
                      "extra": {}}])
        p = alloc.run_once(publish=False)
        assert dead not in p["books"], \
            "the retirement authority is senior to the living-row seed"


class TestTheFundingSuperBookIsClassedBySignal:
    def test_band_barnes_is_funding_not_directional(self):
        """🎸 Barnesy is three FUNDING sleeves (carry / extreme / xsect) named
        for an Australian musician, so no substring marker can see it. Caught
        while it still had zero closes — it would have silently corrupted the
        by_class headline the moment it closed its first trade."""
        assert alloc.book_class("band-barnes-lshadow") == "funding"

    def test_the_registry_is_exact_not_a_widened_marker(self):
        """Widening FUNDING_MARKERS until it caught 'barnes' would catch
        unrelated rows too — the same defect one layer over."""
        assert "barnes" not in alloc.FUNDING_MARKERS
        assert alloc.book_class("band-someoneelse-lshadow") == "directional"

    def test_every_registered_funding_book_is_a_real_row(self):
        """A registry entry that no longer resolves is the stale-reference
        class `audit_doctrine_enforcement::check_ref` exists to catch."""
        import pathlib as _p
        root = _p.Path(__file__).resolve().parents[2]
        tree = (root / "CLAUDE.md").read_text()
        for bot in alloc.FUNDING_BOOKS:
            assert bot in tree, f"{bot} is registered but names no known row"


class TestTheEraTwinIsLiveNotBornDark:
    """[2026-08-05 (kc)] The era twin imports its rule from `golive_readiness`
    (and `experiment_judge` for the stamp parse) behind a try/except, so that a
    grading-surface move can never take the organ down. That is correct AND it
    is the born-dark shape: a missing module degrades to None forever and the
    payload just quietly stops carrying the field.

    So these assert the twin actually SPLITS, not merely that it imports.
    """

    def test_both_era_modules_ship_in_the_image(self):
        import pathlib as _p
        df = (_p.Path(__file__).resolve().parents[2]
              / "Dockerfile.freqtrade").read_text()
        assert "golive_readiness.py" in df, \
            "the era owner must ship or the twin is dark in production"
        assert "experiment_judge.py" in df, \
            "the stamp parser must ship or every close fails to parse"

    def test_the_twin_actually_excludes_pre_era_trades(self):
        """A book with a DECLARED era must report fewer in-era closes than
        all-time. If this returns n_era == n, the era rule is not running and
        the field is decoration."""
        from datetime import datetime, timezone, timedelta
        import sys as _s, os as _o
        _s.path.insert(0, _o.path.join(
            _o.path.dirname(_o.path.abspath(alloc.__file__)), "scripts"))
        from golive_readiness import POLICY_ERA, era_base
        bot = "perps-funding-carry-lshadow"
        iso = POLICY_ERA[era_base(bot)][0]
        cut = datetime.fromisoformat(iso).replace(tzinfo=timezone.utc)
        rows = []
        for d in (-9, -6, -3, 3, 6, 9):        # 3 before the era, 3 after
            ts = cut + timedelta(days=d)
            rows.append({"profit_ratio": 0.01, "profit_abs": 1.0,
                         "open_ts": ts.isoformat(),
                         "close_ts": ts.isoformat(), "extra": {}})
        n_era, _claim, era_iso, src = alloc._era_twin(bot, rows)
        assert n_era == 3, (
            f"expected the 3 post-era closes, got {n_era} — the era rule is "
            f"not running (source={src}, iso={era_iso})")
        assert era_iso is not None and src is not None

    def test_an_undeclared_book_keeps_every_row(self):
        """Fail-safe in the only safe direction: no declared era -> nothing is
        excluded, so the twin can never silently shrink a book's evidence."""
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        rows = [{"profit_ratio": 0.01, "profit_abs": 1.0,
                 "open_ts": (now - timedelta(days=d)).isoformat(),
                 "close_ts": (now - timedelta(days=d)).isoformat(),
                 "extra": {}} for d in range(6)]
        n_era, _c, _i, _s = alloc._era_twin("no-such-book-lshadow", rows)
        assert n_era == 6, "an undeclared book must keep every row"
