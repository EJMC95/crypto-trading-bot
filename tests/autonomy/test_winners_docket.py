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
# --------------------------------------------------------------- [I21] (tt)
# THE PRE-REGISTERED FOLLOW-THROUGH. I21 says a bucket held only by the
# multiplicity referee is "graded on closes AFTER registration, t>=2 on the
# fresh sample alone, never by re-mining the window that generated them" —
# and until 21-Aug nothing enforced it. Measured that morning: 🎫 taker
# `exit:hold` reached n=62 pooled (t=3.53, p=0.0004) and the docket printed
# it under PROVEN WINNING, three days after registering it at n=53. The
# fresh sample was n=9 — above the t-bar, below the MIN_N floor, i.e. NOT
# YET DECIDABLE. These pin the difference between those two statements.

#: a zero-variance list has an undefined t, so every fixture below needs
#: spread — the first draft used [0.02]*30 and graded p=0.5 (sd=0).
def _spread(mean, n, jitter=0.005):
    return [mean + (jitter if i % 2 else -jitter) + jitter * (i % 3) / 3
            for i in range(n)]


def _prereg_bucket(pre, post, key=("bot-pr", "exit", "hold")):
    """Build a bucket registered at T0+... with `pre`/`post` pct lists."""
    rows = [_row(p, i, "long_hold") for i, p in enumerate(pre)]          # T0+0h..
    rows += [_row(p, 24 * 30 + i, "long_hold") for i, p in enumerate(post)]
    since = (T0 + timedelta(hours=len(pre))).isoformat()
    wd.PRE_REGISTERED[key] = dict(since=since, n=len(pre), t=9.9,
                                  mean_pct=1.0, source="test")
    return key, rows, since


def _drop(key):
    wd.PRE_REGISTERED.pop(key, None)


def test_a_pre_registered_bucket_is_never_crowned_on_the_pooled_window():
    """The exact 21-Aug defect: pooled clears BH, so it printed PROVEN."""
    key, rows, _ = _prereg_bucket(_spread(0.02, 30), _spread(0.02, 5))
    try:
        graded = wd.grade_buckets({key: rows})
        assert graded[key]["p"] < 0.001, "fixture must clear BH pooled"
        txt, winners = wd.report(graded)
        assert key not in winners, "a re-mined window may not crown a winner"
        assert "PROVEN WINNING: none" in txt
        assert "PRE-REGISTERED FOLLOW-THROUGH" in txt
        assert "would have been crowned PROVEN" in txt, \
            "the report must SAY the pooled window would have crowned it"
    finally:
        _drop(key)


def test_the_fresh_sample_is_only_closes_after_registration():
    key, rows, _ = _prereg_bucket(_spread(0.02, 30), _spread(-0.01, 4))
    try:
        ft = wd.grade_buckets({key: rows})[key]["prereg"]
        assert ft["n"] == 4, ft
        assert ft["mean_pct"] < 0, "the fresh closes are the LOSERS here"
    finally:
        _drop(key)


def test_a_fresh_sample_below_the_floor_is_undecided_however_good_its_t():
    """n=9 at t=2.99 was the real reading. Below MIN_N it decides NOTHING."""
    key, rows, _ = _prereg_bucket(_spread(0.02, 30), _spread(0.05, 9))
    try:
        ft = wd.grade_buckets({key: rows})[key]["prereg"]
        assert ft["n"] == 9 and ft["n"] < wd.MIN_N
        assert ft["t"] >= 2.0, "fixture must clear the t-bar so the FLOOR is what bites"
        assert ft["verdict"] == "undecided", ft
    finally:
        _drop(key)


def test_a_fresh_sample_at_the_floor_can_confirm_and_can_refuse():
    key, rows, _ = _prereg_bucket(_spread(0.02, 30), _spread(0.025, 12))
    try:
        ft = wd.grade_buckets({key: rows})[key]["prereg"]
        assert ft["n"] >= wd.MIN_N and ft["verdict"] == "confirmed", ft
    finally:
        _drop(key)
    key, rows, _ = _prereg_bucket(_spread(0.02, 30), [0.02, -0.03] * 6)
    try:
        ft = wd.grade_buckets({key: rows})[key]["prereg"]
        assert ft["n"] >= wd.MIN_N and ft["verdict"] == "not_confirmed", ft
    finally:
        _drop(key)


def test_the_two_live_registrations_are_declared_with_their_record():
    """A registration is a COMMITMENT — the at-registration stats are the
    record and must survive in the table, not be re-derived from today."""
    taker = wd.PRE_REGISTERED[("lighter-ticket-taker-lshadow", "exit", "hold")]
    assert taker["n"] == 53 and taker["t"] == 2.65, taker
    avo = wd.PRE_REGISTERED[("freqtrade-avo-maria-lshadow", "book", "*")]
    assert avo["n"] == 12 and avo["t"] == 2.31, avo
    # [2026-09-02 (wm)] Re-aimed per I26: this asserted every `since` began
    # "2026-08-18" — a snapshot of the table's first two rows that reddened the
    # first NEW registration (👩 mum), i.e. it pinned the table's narrowness,
    # not the commitment property. The property: every row carries a parseable
    # UTC `since` and its at-registration record, and the founding rows above
    # stay byte-stable (asserted explicitly there).
    for r in wd.PRE_REGISTERED.values():
        assert r["since"][:4].isdigit() and "T" in r["since"], r
        assert r["n"] >= wd.MIN_N and r["t"] > 0 and r["mean_pct"] > 0, r
        assert r["source"], r


def test_a_pre_registered_bucket_is_not_double_reported_as_on_its_way():
    """It has its own section; listing it twice invites quoting the pooled t."""
    key, rows, _ = _prereg_bucket(_spread(0.01, 30), _spread(0.01, 3))
    try:
        txt, _w = wd.report(wd.grade_buckets({key: rows}))
        assert txt.count(f"{key[0]} [{key[1]}:{key[2]}]") == 1, txt
    finally:
        _drop(key)
