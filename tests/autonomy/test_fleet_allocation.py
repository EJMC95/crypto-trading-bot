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
import pytest

import fleet_allocation as alloc

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
