"""The MTM equity series must exist for the books the go-live gate can promote.

INCIDENT (2026-07-31, (hq)). `(hl)` shipped `bot_pnl_store.snapshot_equity`
because `golive_readiness.stats()` — the grader for the rule deciding whether a
$1,000 shadow book may ever hold real money — accumulates REALISED closed-trade
P&L only. For a book that HOLDS most of the time, most of its drawdown is open
and invisible to the bar. `(hl)`'s own conclusion named the book to re-grade
first:

    "Re-grade carry under MTM before anyone reads its score as unchanged: carry
     is five of six bars from go-live, so a stricter drawdown definition lands
     on it first."

It then wired the two RIDERS — `lighter_trend_bot` and `lighter_index_bot` —
and **not** 🌾 carry. Measured on 31-Jul, `bot_state_history` held a ':equity'
series for exactly `crypto-trend-daily-lshadow` and `equities-regime-lshadow`.
So the clock the go-live conversation was told to wait for had never started on
the only book the conversation is about, and the carried review priority that
depends on it ("the MTM number should exist BEFORE the go-live conversation",
window closing ~10-11 Aug) rested on a false premise.

The second book wired at (hq) is where the realised-only bar is most blind,
measured rather than argued: ⚖️ `perps-funding-spread-lshadow` reads +$7.29
realised over 48 closes while its published row reads -$27.47 — a **-$34.76
open loss across 24 legs** — and the grader scores its maxDD at **0.2%**.

WHY THIS FILE EXISTS RATHER THAN A ONE-OFF FIX: wiring carry closes the
instance. The CLASS is "a book that holds, and that the gate can promote,
accrues no MTM series and nobody notices for a week". A book is added here
deliberately or the build goes red.
"""
import ast
import datetime as _dt
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

#: Books that HOLD positions and that `golive_readiness` grades as living
#: candidates. Each MUST call `store.snapshot_equity`.
MTM_REQUIRED = {
    "funding_carry_bot.py":
        "🌾 carry — the fleet's nearest go-live candidate; (hl) named it FIRST "
        "and did not wire it",
    "lighter_funding_spread_bot.py":
        "⚖️ Counterweight — largest measured realised-vs-MTM gap in the fleet "
        "(-$34.76 open against a 0.2% realised maxDD)",
    "lighter_trend_bot.py":
        "🌊 Tide Rider — holds for weeks; wired by (hl)",
    "lighter_index_bot.py":
        "📊 Index Rider — long on 64% of days; the book (hl) measured, wired by it",
    # [2026-08-05] ranked-plan item ② — moved up from MTM_PENDING. The code
    # edit was the reviewable half all along; what stays operator-gated is
    # the DEPLOY (both Farmer arms + the live Taker ship at the next marker
    # push; the Taker's shadow arm auto-deploys with freqtrade-bots).
    "lighter_funding_bot.py":
        "💸 Funding Farmer, BOTH arms — the live pair's books were the last "
        "gradeable holders dark on the series the (ia) bar reads",
    "lighter_ticket_taker.py":
        "🎫 Ticket Taker, BOTH arms — live money on divergence-short; its "
        "open drawdown was invisible to the bar that governs it",
}

#: Books that publish `open_trades` but are NOT yet wired, each with the reason.
#: This is the (hq) equivalent of `BORN_DARK_OK`: a deliberate omission is
#: DECLARED, silence is not an option. Moving a book from here to MTM_REQUIRED
#: is the act of putting it in front of the gate.
MTM_PENDING = {
    "lighter_dislocation_bot.py":
        "🧲 Snap Back — flat most of the time (0 open at time of writing) and "
        "mean is negative, so it is not a promotion candidate",
    "lighter_perp_sniper.py":
        "🎯 Perp Sniper — event-class, n=5; nowhere near the closes bar",
    "lighter_family_bot.py":
        "the four family books — short holds, and their drawdown is already "
        "close to realised (measured |unrealised| <= $5.31)",
    "lighter_momentum_bot.py": "retired (Trail Blazer), idles behind a guard",
    "hyperliquid_momo_bot.py": "retired 15-Jul, idles behind a guard",
    "hyperliquid_perps_bot.py": "retired (Bounce Catcher), idles behind a guard",
    "listing_sniper.py": "retired 17-Jul (LIGHTER-ONLY cut), idles behind a guard",
    "parliament/strategies.py":
        "🏛️ the Parliament — shadow-only forever until the standard gate; its "
        "six books are graded by Howard, not by golive_readiness",
    "freqtrade_pnl_poller.py": "a POLLER, not a book — holds nothing itself",
}


def _calls_snapshot_equity(path):
    """True when the module really CALLS `snapshot_equity` — by AST, not by
    substring. A docstring or a comment mentioning it (this repo documents its
    incidents at length) must not count as wiring."""
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            name = (fn.attr if isinstance(fn, ast.Attribute)
                    else fn.id if isinstance(fn, ast.Name) else None)
            if name == "snapshot_equity":
                return True
    return False


@pytest.mark.parametrize("mod", sorted(MTM_REQUIRED))
def test_gradeable_holding_books_accrue_an_mtm_series(mod):
    """The instance: each of these must actually call snapshot_equity."""
    p = ROOT / mod
    assert p.exists(), f"{mod} moved — update MTM_REQUIRED"
    assert _calls_snapshot_equity(p), (
        f"{mod} publishes but never calls store.snapshot_equity — "
        f"{MTM_REQUIRED[mod]}. The go-live drawdown bar reads REALISED P&L "
        "only, so without this series the book's open drawdown is invisible "
        "to the rule that governs real money.")


def test_every_publishing_book_is_either_wired_or_DECLARED():
    """The class. A new holding book that publishes `open_trades` and accrues
    no MTM series must be a DECLARED decision, not an oversight — the
    `BORN_DARK_OK` idiom. This is what stops (hq) recurring on book number
    twelve."""
    offenders = []
    for p in sorted(ROOT.glob("*.py")) + sorted(ROOT.glob("parliament/*.py")):
        rel = str(p.relative_to(ROOT))
        if rel in ("bot_pnl_store.py",):          # the publisher itself
            continue
        src = p.read_text()
        if "store.publish(" not in src or "open_trades=" not in src:
            continue
        if _calls_snapshot_equity(p):
            continue
        if rel not in MTM_PENDING:
            offenders.append(rel)
    assert not offenders, (
        f"{offenders} publish open positions but accrue no MTM equity series "
        "and are not declared in MTM_PENDING. Wire them, or declare the "
        "omission WITH A REASON — a silent omission is exactly how 🌾 carry "
        "went a day being called 'five of six bars from go-live' on a "
        "drawdown number that could not see its open book.")


def test_the_declarations_carry_a_real_reason():
    """A declaration that says nothing is a rubber stamp."""
    for table in (MTM_REQUIRED, MTM_PENDING):
        for mod, why in table.items():
            assert why and len(why) > 25, f"{mod}: declare WHY, in a sentence"


def test_pending_declarations_are_not_stale():
    """A book that got wired must LEAVE MTM_PENDING, or the table becomes a
    list of things that used to be true — the rot this repo keeps finding in
    prose. (Its counterpart, a test that fails on GOOD NEWS, is avoided: this
    asserts the table tracks reality, not that anything stays unwired.)"""
    stale = [m for m in MTM_PENDING
             if (ROOT / m).exists() and _calls_snapshot_equity(ROOT / m)]
    assert not stale, (
        f"{stale} now call snapshot_equity but are still declared PENDING — "
        "move them to MTM_REQUIRED so the guard protects them")


# ---------------------------------------------------------------------------
# THE READ SIDE ((iz), 2026-08-04). Everything above guards the WRITE half of
# the wire; nothing exercised the READ half, and it was dead on arrival:
# `golive_readiness.equity_series` called `store.load_history(...)` — a
# function `bot_pnl_store` has never defined (the read side of `save_history`
# is `fetch_state_history`) — and its bare `except Exception: return []`
# swallowed the AttributeError. Every book graded `mtm_why: "no usable equity
# series"`, so the (ia) MTM drawdown bar — built precisely so an always-in
# book like ⚖️ Counterweight cannot pass the 15% maxDD bar on realised-only
# data — was structurally inert from the day it shipped. The selftest pinned
# only the DEGENERATE direction (`equity_series("nope", store=object()) ==
# []`): a value-free green, exactly the class the (hj) doctrine names.
#
# These tests run the REAL publisher and the REAL reader end-to-end —
# snapshot_equity -> save_history -> fetch_state_history -> equity_series ->
# mtm_drawdown -> apply_mtm — and demand a NON-degenerate result. Only the
# transport is simulated: `_FakeConn` replays whatever the real save_history
# INSERTs back through the real fetch_state_history's SELECT (same key
# filter, same NEWEST-FIRST order, same LIMIT), so the payload shape is the
# publisher's own, never a hand-written fixture. Mutation-verified: renaming
# the equity_series call back to `load_history` turns both tests red.
# ---------------------------------------------------------------------------

class _FakeCursor:
    def __init__(self, db):
        self._db = db
        self._rows = []
        self.rowcount = 0

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        s = " ".join(str(sql).split()).lower()
        if s.startswith("insert into bot_state_history"):
            key, payload = params            # exactly save_history's two binds
            self._db.rows.append((key, self._db.tick(), payload))
        elif s.startswith("select ts, payload from bot_state_history"):
            key, limit = params
            hit = [r for r in self._db.rows if r[0] == key]
            hit.sort(key=lambda r: r[1], reverse=True)   # ORDER BY ts DESC
            self._rows = [(ts, payload) for _, ts, payload in hit[:int(limit)]]
        # CREATE TABLE / CREATE INDEX / DELETE (prune): accepted, no-op

    def fetchall(self):
        return list(self._rows)


class _FakeConn:
    """In-memory stand-in for the Postgres CONNECTION only. Rows are whatever
    the real `save_history` binds; the DB clock (`now()`) advances one hour
    per write so a 240-write series spans ~10 days — past both MTM floors."""

    def __init__(self):
        self.rows = []
        self._now = _dt.datetime(2026, 8, 1, tzinfo=_dt.timezone.utc)

    def tick(self):
        self._now += _dt.timedelta(hours=1)
        return self._now

    def cursor(self):
        return _FakeCursor(self)

    def close(self):
        pass


@pytest.fixture
def store_on_fake_db(monkeypatch):
    import bot_pnl_store as store            # noqa: PLC0415
    conn = _FakeConn()
    monkeypatch.setattr(store, "_get_conn", lambda: conn)
    monkeypatch.setattr(store, "_history_table_ready", False)
    return store


def test_grader_reads_the_series_the_publisher_writes(store_on_fake_db):
    """The incident pin: a series the publisher wrote must come back
    NON-degenerate through the grader's own read path, and a planted MTM
    drawdown must reach — and decide — the maxDD bar."""
    import golive_readiness as g             # noqa: PLC0415
    store = store_on_fake_db
    bot = "perps-funding-spread-lshadow"
    # 240 hourly samples (~10d): 1000 -> 1100 -> 900, i.e. a $200
    # peak-to-trough = 20% of the $1,000 book, against the 15% bar.
    for i in range(240):
        if i < 100:
            eq = 1000.0 + i
        elif i < 200:
            eq = 1100.0 - 2.0 * (i - 100)
        else:
            eq = 900.0
        assert store.snapshot_equity(bot, eq, open_trades=3) is True, \
            "the publisher's write failed — the series never even started (I4)"

    series = g.equity_series(bot, store=store)
    assert len(series) == 240, (
        "equity_series returned a degenerate series for a book whose history "
        "the publisher just wrote — the (iz) failure: the grader calling a "
        "read function the store does not define, behind a bare except")
    assert max(e for _, e in series) == 1100.0
    assert min(e for _, e in series) == 900.0

    mtm = g.mtm_drawdown(series)
    assert mtm is not None and mtm["n"] == 240
    assert mtm["max_dd_usd"] == pytest.approx(-200.0)
    assert mtm["max_dd_frac"] == pytest.approx(0.2)
    assert mtm["days"] > 7

    folded = g.apply_mtm({"max_dd_frac": 0.002}, mtm)
    assert folded["maxdd_basis"] == "mtm", (
        "a thick MTM series must DECIDE the bar, not fall back to realised")
    assert folded["max_dd_frac"] == pytest.approx(0.2)
    assert "mtm_why" not in folded


def test_a_young_series_reads_thin_not_absent(store_on_fake_db):
    """After the fix, a book with a young series must publish 'series too
    thin to decide' — NEVER 'no usable equity series', which was the (iz)
    symptom on all 18 books (the grader could not read ANY series)."""
    import golive_readiness as g             # noqa: PLC0415
    store = store_on_fake_db
    bot = "perps-funding-carry-lshadow"
    for i in range(24):
        assert store.snapshot_equity(bot, 1000.0 + i) is True

    series = g.equity_series(bot, store=store)
    assert len(series) == 24

    folded = g.apply_mtm({"max_dd_frac": 0.002}, g.mtm_drawdown(series))
    assert folded["maxdd_basis"] == "realised"
    assert "too thin" in folded.get("mtm_why", ""), (
        f"got mtm_why={folded.get('mtm_why')!r} — a young series must read "
        "'thin', not 'absent'; the floors stand, the read works")
