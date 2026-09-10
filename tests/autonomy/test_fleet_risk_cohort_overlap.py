"""[2026-09-09 (zv)] THE SAME BASE HELD BY TWO REAL-MONEY BOOKS IS ONE BET
HELD TWICE, AND NOTHING SAID SO PER COHORT.

Measured on the 9-Sep 06:03Z payload: 👩 mum (4 legs) and 🙏 avo (6 legs) both
held SPY and XAU. fleet_risk's only view of it, `pair_concentration`, pools
paper into the count, so `SPY: 2` there cannot say whether that is two live
books or a live book and its paper twin. This publishes the per-cohort view
beside the (wp)/(wy) cohort split — ADVISORY (I16): a number, no actuator.
The per-symbol pileup cap stays pooled and stays the enforcing surface;
scoping it per cohort changes which trades the live books take and owes its
expectancy price first (I19).
"""
import ast
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

import fleet_risk as fr   # noqa: E402

pytestmark = pytest.mark.autonomy

VENUES = {"freqtrade-mum": "lighter_live", "freqtrade-avo-maria": "lighter_live",
          "lighter-ticket-taker": "lighter_shadow"}


def test_the_9_sep_shape_reads_two_live_duplicates_and_no_paper_in_them():
    expo = [("freqtrade-mum", "SPY", "long"), ("freqtrade-mum", "XAU", "long"),
            ("freqtrade-mum", "COIN", "long"), ("freqtrade-mum", "MORPHO", "long"),
            ("freqtrade-avo-maria", "BTC", "long"), ("freqtrade-avo-maria", "MON", "long"),
            ("freqtrade-avo-maria", "SPY", "long"), ("freqtrade-avo-maria", "XAU", "long"),
            ("freqtrade-avo-maria", "XMR", "long"), ("freqtrade-avo-maria", "NVDA", "long"),
            ("lighter-ticket-taker", "SPY", "long")]
    out = fr.cohort_overlap(expo, VENUES)
    assert out["live"]["overlap"] == {"SPY": 2, "XAU": 2}, out
    assert out["live"]["overlap_n"] == 2 and out["live"]["long_distinct"] == 8, out
    assert out["shadow"] == {"long_distinct": 1, "overlap": {}, "overlap_n": 0}, out


def test_a_short_is_not_a_long_pileup_and_a_book_counts_once_per_base():
    expo = [("a", "ETH", "short"), ("b", "ETH", "long"),
            ("c", "SOL", "long"), ("c", "SOL", "long")]
    out = fr.cohort_overlap(expo, {"a": "lighter_live", "b": "lighter_live",
                                   "c": "lighter_live"})
    assert out["live"]["overlap"] == {}, out
    assert out["live"]["long_distinct"] == 2, out


def test_an_unknown_venue_reads_as_modelled_never_as_real_money():
    """venue_cohort's own fail-safe direction: a row the light did not file
    under a venue is paper, so it can never inflate the real-money view."""
    out = fr.cohort_overlap([("x", "SPY", "long"), ("freqtrade-mum", "SPY", "long")],
                            {"freqtrade-mum": "lighter_live"})
    assert out["live"]["overlap"] == {} and out["shadow"]["long_distinct"] == 1, out


def test_the_ordering_puts_the_deepest_pileup_first():
    expo = [(b, "AAA", "long") for b in "abc"] + [(b, "BBB", "long") for b in "ab"]
    out = fr.cohort_overlap(expo, {b: "lighter_live" for b in "abc"})
    assert list(out["live"]["overlap"].items()) == [("AAA", 3), ("BBB", 2)]


def test_junk_never_raises():
    for expo, venues in ((None, None), ([], {}), ([("a", None, "long")], {}),
                         ([("a", "x", None)], None)):
        fr.cohort_overlap(expo, venues)


def test_the_view_is_actually_published_under_cohorts():
    """AST: main() must call cohort_overlap and the risk payload's `cohorts`
    entry must be the merged map, not a fresh cohort_view() — otherwise the
    number exists and reaches no reader (the (iz) shape)."""
    src = open(os.path.join(os.path.dirname(fr.__file__), "fleet_risk.py")).read()
    tree = ast.parse(src)
    main = next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "main")
    called = {n.func.id for n in ast.walk(main)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "cohort_overlap" in called, "computed nowhere"
    published = [v for n in ast.walk(main) if isinstance(n, ast.Dict)
                 for k, v in zip(n.keys, n.values)
                 if isinstance(k, ast.Constant) and k.value == "cohorts"]
    assert published, "no `cohorts` key in the payload"
    assert any(isinstance(v, ast.Name) and v.id == "_cohort_payload" for v in published), \
        "the `cohorts` entry must be the merged map"


def test_cohort_view_is_unchanged_so_every_old_reader_still_reads_it():
    v = fr.cohort_view({"live": 10, "shadow": 17})
    assert set(v) == {"live", "shadow"}
    assert set(v["live"]) == {"long_positions", "long_budget", "light"}
