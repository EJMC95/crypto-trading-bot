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
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]

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
}

#: Books that publish `open_trades` but are NOT yet wired, each with the reason.
#: This is the (hq) equivalent of `BORN_DARK_OK`: a deliberate omission is
#: DECLARED, silence is not an option. Moving a book from here to MTM_REQUIRED
#: is the act of putting it in front of the gate.
MTM_PENDING = {
    "lighter_funding_bot.py":
        "LIVE Funding Farmer — real money; a publish-path change to a live "
        "image is an operator-gated deploy, not a review-run edit",
    "lighter_ticket_taker.py":
        "LIVE Ticket Taker — same reason as the Farmer",
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
