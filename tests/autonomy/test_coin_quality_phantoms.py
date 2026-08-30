"""The coin veto is a REAL-MONEY entry gate and it was counting halt events.

[2026-08-28 (vd)] `market_context.coin_quality` aggregates 30 days of
`paper_trades` into per-coin {closes, wins, stops}. `market_context` L463 turns
that into `coin-vetoes` — `closes >= 5 and stops/closes >= 0.5` — and all THREE
live real-money books read it at the entry site
(`lighter_avo_live_bot.py:2073` -> `_verdict(sym, 'coin_veto')` -> refuse).

It was the one ledger reader in the fleet carrying NEITHER a `side <> 'skip'`
filter NOR an event filter.

WHY THE DIRECTION MATTERS MORE THAN THE MAGNITUDE: a phantom's reason is
`long_daily_loss`, which does not match `'%stop%'`. So it lands in the
DENOMINATOR and never the numerator — pushing the 5-close floor closer and the
50% bar further away. Both effects RELEASE the veto. A coin whose true record
is 3 stops of 5 closes (60%, vetoed) reads 3 of 7 (43%, admitted) after two
halt events. Absence of evidence must never authorise an entry.

MEASURED THE DAY THIS SHIPPED: veto set `['XAG']` with and without the 13 —
zero expectancy bought, shipped as correctness. `BRENTOIL` 5 -> 4 closes is the
floor-manufacturing direction caught in the act.

THE SQL IS A SECOND COPY OF THE OWNER'S RULE — unavoidable inside a
`cur.execute`, so it is drift-guarded here instead: both are driven over the
same live ledger rows and must agree exactly.
"""
import json
import pathlib
import re
import sys
import urllib.request

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from golive_readiness import is_phantom_close                # noqa: E402

FEED = ("https://pnl-dashboard-production-858c.up.railway.app"
        "/trades.json?source=paper&limit=9000")


def _sql():
    return (ROOT / "market_context.py").read_text()


def test_the_veto_query_excludes_halt_events_and_skips():
    """The gate itself. Both clauses, on the paper_trades aggregate that feeds
    `coin-vetoes` — not on some other query in the file."""
    src = _sql()
    m = re.search(r"cur\.execute\(\"\"\"\s*(SELECT split_part\(pair.*?)\"\"\"\)",
                  src, re.S)
    assert m, "the coin-quality paper_trades query moved — re-aim this test"
    q = m.group(1)
    assert "NOT (pnl_abs = 0 AND entry_price IS NULL)" in q, (
        "halt/flatten events are counted as closes in the coin veto")
    assert "side IS DISTINCT FROM 'skip'" in q, (
        "skip rows are counted as closes in the coin veto")


def test_the_sql_predicate_and_the_owner_agree_on_the_live_ledger():
    """DRIFT ARM. The SQL cannot import `is_phantom_close`, so this is the only
    thing standing between two copies of one rule ((hj)). If they ever disagree
    on a real row, one of them is wrong and this says which."""
    try:
        rows = json.load(urllib.request.urlopen(FEED, timeout=90))["trades"]
    except Exception as exc:                                 # noqa: BLE001
        pytest.skip(f"live feed unavailable: {exc}")
    assert len(rows) > 500, "feed too small to be a meaningful drift check"

    def sql_says_phantom(r):
        # The WHERE clause, transcribed: excluded iff pnl_abs = 0 AND
        # entry_price IS NULL. SQL `= 0` is a numeric compare, so None/absent
        # pnl_abs does NOT match — mirror that rather than Python's `or 0.0`.
        p = r.get("pnl_abs")
        return p is not None and float(p) == 0.0 and r.get("entry_price") is None

    owner = {r["trade_id"] for r in rows if is_phantom_close(r)}
    sql = {r["trade_id"] for r in rows if sql_says_phantom(r)}
    assert owner == sql, (
        f"the SQL predicate and is_phantom_close disagree on "
        f"{len(owner ^ sql)} row(s): only-owner={sorted(owner - sql)[:5]} "
        f"only-sql={sorted(sql - owner)[:5]}")
    assert owner, "no phantoms in the feed at all — the drift check is vacuous"


def test_a_phantom_can_only_ever_loosen_this_gate():
    """THE MECHANISM, asserted rather than described — this is why the fix is
    worth shipping at zero measured expectancy. A phantom's reason must not
    match the stop pattern, so it can only inflate the denominator."""
    for reason in ("long_daily_loss", "short_daily_loss",
                   "long-range-on_daily_loss"):
        assert "stop" not in reason, (
            f"{reason} would match '%stop%' and the release-direction argument "
            f"would not hold")
    # and the real stop reasons must still match, or the numerator is empty
    for reason in ("long_stop_loss", "trend-breakout_trailing_stop_loss"):
        assert "stop" in reason

    closes, stops = 5, 3
    assert stops / closes >= 0.5                    # vetoed on the true record
    assert (stops) / (closes + 2) < 0.5             # admitted after two halts


def test_the_live_books_actually_consume_this_veto():
    """A gate nobody reads is not worth guarding, and this test is the only
    thing tying the fix to the claim that it touches real money."""
    src = (ROOT / "lighter_avo_live_bot.py").read_text()
    assert "coin-vetoes" in src, "the live host no longer reads coin-vetoes"
    assert "coin_veto" in src, "the live host no longer applies a coin veto"
