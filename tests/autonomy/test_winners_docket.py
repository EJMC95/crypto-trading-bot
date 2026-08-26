"""[(qd)/I21] The winners' docket — losing gets a refereed docket; winning
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
    """LITERAL nine, not `MIN_N - 1` — a fixture derived from the constant
    tracks any mutation of it (a 9-row bucket passed a floor lowered to 2 and
    this test stayed green: measured, mutation M3, 18-Aug)."""
    assert wd.MIN_N >= 10, "the luck floor is doctrine (I16), not a tunable"
    bk = wd.buckets_of({"bot-lucky": [_row(0.02, i, "long_hold")
                                      for i in range(9)]})
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


def test_phantom_closes_never_reach_the_referee():
    """[2026-08-26 daily review] A halt/flatten EVENT is not a trade.

    THE INCIDENT: the docket graded 13 phantom rows — $0.00 P&L with no entry
    price — and all 13 sat on the two REAL-MONEY books
    (`freqtrade-avo-maria-lighter` 9, `freqtrade-georgia-lighter` 4). That put
    a real-money row on the docket's "ON THEIR WAY [to proven winning]" list
    at n=13/t=1.46 when its true traded n is 4, below the MIN_N floor.
    `golive_readiness` had filtered these since (th); the docket had not, so
    the fleet's two graders disagreed about the same real-money ledger.

    The direction is the reason this matters: a block of exact-$0.00 rows does
    not merely inflate n, it SHRINKS the sample variance, so it biases `t`
    UPWARD — the referee erred toward crowning a real-money book.
    """
    import golive_readiness as gr

    # (1) the signature is the GATE'S OWN, by identity — never a second copy
    assert wd.gr.is_phantom_close is gr.is_phantom_close
    src = (ROOT / "scripts" / "winners_docket.py").read_text()
    assert "def is_phantom_close" not in src, \
        "a second copy of the phantom signature is a second rule"

    # (2) the filter actually runs in the docket's own loader
    real = [dict(bot="bk", profit_ratio=0.01, profit_abs=1.0, open_rate=100.0,
                 close_ts=(T0 + timedelta(hours=i)).isoformat(),
                 open_ts=(T0 + timedelta(hours=i - 1)).isoformat(),
                 exit_reason="long_hold", enter_tag="long") for i in range(12)]
    phantom = [dict(bot="bk", profit_ratio=0.0, profit_abs=0.0, open_rate=None,
                    close_ts=(T0 + timedelta(hours=200 + i)).isoformat(),
                    open_ts=(T0 + timedelta(hours=199 + i)).isoformat(),
                    exit_reason="long_daily_loss", enter_tag="long")
               for i in range(9)]
    kept = wd.era_scoped_rows(real + phantom)["bk"]
    assert len(kept) == 12, f"phantom rows reached the referee: {len(kept)}"
    assert all(r["abs"] != 0.0 or r["exit"] != "long_daily_loss" for r in kept)

    # (3) FAIL-OPEN, exactly as the gate defines it: a real $0.00 close that
    #     HAS an entry price is a genuine scratch trade and must survive, or
    #     the filter becomes a silent sample-shrinker.
    scratch = dict(bot="bk2", profit_ratio=0.0, profit_abs=0.0, open_rate=100.0,
                   close_ts=(T0 + timedelta(hours=5)).isoformat(),
                   open_ts=T0.isoformat(), exit_reason="long_hold",
                   enter_tag="long")
    assert len(wd.era_scoped_rows([scratch])["bk2"]) == 1, \
        "a real scratch close was dropped — the filter exceeded its signature"
