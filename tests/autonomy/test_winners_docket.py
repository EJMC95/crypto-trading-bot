"""[(qa)/I21] The winners' docket — losing gets a refereed docket; winning
gets the SAME instrument, with the same defenses against fooling ourselves.

Pins the four properties that make the docket honest rather than a
luck-crowning machine:
  * outcome-conditioned exit buckets NEVER reach the referee (I7 — a tp
    bucket is a winner by construction; measured 18-Aug: three such
    "winners" at t up to 75 dissolved the moment they were excluded);
  * identical row-sets count ONCE (a one-tag book would otherwise enter the
    referee four times and dilute every other bucket);
  * the MIN_N floor stops luck BEFORE the statistics (I16 — a consistent
    3-close streak is mathematically significant, which is exactly why it
    must never be tested);
  * the era boundary is the GATE'S OWN era_rows, by identity — a second copy
    would let the docket and the gate disagree about the same ledger ((hj)).
"""
import importlib.util
import pathlib
import sys
from datetime import datetime, timedelta, timezone

ROOT = pathlib.Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "winners_docket", ROOT / "scripts" / "winners_docket.py")
wd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wd)

T0 = datetime(2026, 8, 1, tzinfo=timezone.utc)


def _row(pct, i, exit_reason, tag=""):
    return dict(pct=pct, abs=pct * 100, exit=exit_reason, tag=tag,
                closed=T0 + timedelta(hours=i))


def test_outcome_conditioned_exits_never_reach_the_referee():
    rows = [_row(0.04, i, "short_take_profit") for i in range(20)]
    bk = wd.buckets_of({"bot-x": rows + [_row(-0.06, 90 + i, "short_stop")
                                         for i in range(20)]})
    keys = {k[2] for k in bk if k[1] == "exit"}
    assert not any("take_profit" in k or "stop" in k for k in keys), keys
    # neutral exits ARE admissible — mixed with a second family so the
    # bucket is not the whole book (dedup would then rightly collapse it)
    rows2 = [_row(0.01, i, "long_hold") for i in range(20)] \
        + [_row(-0.005, 50 + i, "long_flip") for i in range(20)]
    bk2 = wd.buckets_of({"bot-y": rows2})
    assert ("bot-y", "exit", "long_hold") in bk2
    assert ("bot-y", "exit", "long_flip") in bk2


def test_identical_row_sets_count_once():
    """A one-tag, one-side, one-exit book is ONE sample, not four."""
    rows = [_row(0.01, i, "long_hold", tag="long-dip") for i in range(15)]
    bk = wd.buckets_of({"bot-z": rows})
    assert len(bk) == 1
    assert next(iter(bk))[1] == "book", "the least specific key survives"


def test_the_min_n_floor_stops_luck_before_the_statistics():
    bk = wd.buckets_of({"bot-lucky": [_row(0.02, i, "long_hold")
                                      for i in range(wd.MIN_N - 1)]})
    assert not bk


def test_bh_referee_math():
    """Hand-computed fixture: m=4, fdr=0.05 -> bars 0.0125/0.025/0.0375/0.05."""
    surv = wd.bh_survivors([("a", 0.001), ("b", 0.02), ("c", 0.2), ("d", 0.9)],
                           fdr=0.05)
    assert surv == {"a", "b"}, surv
    assert wd.bh_survivors([], 0.05) == set()
    assert wd.bh_survivors([("x", 0.9)], 0.05) == set()


def test_t_tail_is_exact():
    assert abs(wd.t_sf(2.228, 10) - 0.025) < 1e-3
    assert abs(wd.t_sf(0.0, 5) - 0.5) < 1e-12


def test_the_era_rule_is_the_gates_own_by_identity():
    import golive_readiness as gr
    assert wd.gr.era_rows is gr.era_rows
    src = (ROOT / "scripts" / "winners_docket.py").read_text()
    assert "def era_rows" not in src, "a second copy of the era rule is a second rule"


def test_the_ledger_read_is_the_quarantined_fetch():
    src = (ROOT / "scripts" / "winners_docket.py").read_text()
    assert "fetch_paper_trades" in src
    assert "psycopg2" not in src and ".execute(" not in src, \
        "no raw SQL — the quarantine lives in the fetch"
