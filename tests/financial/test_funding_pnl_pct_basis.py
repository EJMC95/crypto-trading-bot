"""[2026-08-20 (sb)] A FUNDING BOOK WAS GRADED ON ITS PRICE RETURN ALONE.

⚖️ Counterweight's caller computes `total = price_pnl + accr`, so `pnl_abs` has
always carried funding — while `pnl_pct`, the field the GO-LIVE GATE grades on
(`mean_pct`, `t`), was the pure price move. Two fields, two bases, and the bar
that decides real money read the one that discards the book's entire thesis.

Measured on the 27 closes /trades.json still exposes: pnl_pct equalled the price
return on 27 of 27 rows, while pnl_abs/pnl_pct ranged 4.4-21.1 (CoV 108%) — that
spread is the funding. Re-based, those trades read -0.109%/trade against the
-0.392% the gate sees. The contradiction needs no clip assumption: the percentage
claims -0.392%/trade over 27 trades while the dollars over the same trades are
-$0.15, i.e. flat. Both cannot be true.

This is a MEASUREMENT fix. No entry, exit or size moves.
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import lighter_funding_spread_bot as fs  # noqa: E402


def _capture(monkeypatch):
    seen = {}
    monkeypatch.setattr(fs.store, "publish_paper_trade",
                        lambda bot, **kw: seen.update(kw))
    return seen


def test_pnl_pct_is_the_total_return_when_the_notional_is_known(monkeypatch):
    """$100 leg, +$1 price and +$4 funding => +5% total, NOT the +1% price move.
    Before the fix this recorded 0.01 and the gate graded a 5% trade as 1%."""
    seen = _capture(monkeypatch)
    fs._record_close("b", "ETH", 100.0, 1, 101.0, 5.0, True, "tp", True,
                     notional=100.0)
    assert seen["pnl_abs"] == 5.0
    assert seen["pnl_pct"] == 0.05, (
        "pnl_pct must share pnl_abs's basis — funding included")


def test_the_two_fields_can_no_longer_disagree(monkeypatch):
    """The structural invariant, which is what actually failed: pnl_abs and
    pnl_pct must be the same quantity in different units."""
    seen = _capture(monkeypatch)
    for total, notional in ((5.0, 100.0), (-2.5, 50.0), (0.0, 33.0)):
        fs._record_close("b", "ETH", 100.0, 1, 90.0, total, True, "tp", True,
                         notional=notional)
        assert seen["pnl_pct"] * notional == seen["pnl_abs"], (
            "pnl_pct * notional must reconstruct pnl_abs exactly")


def test_a_losing_price_move_with_bigger_funding_reads_POSITIVE(monkeypatch):
    """The case the old basis inverted, and the reason this matters for a
    keep-or-retire call: a delta-neutral funding book routinely takes a small
    price loss to collect a larger carry. Priced on the move alone that is a
    losing trade; priced on the total it is a winner."""
    seen = _capture(monkeypatch)
    fs._record_close("b", "ETH", 100.0, 1, 99.0, +3.0, True, "decay", True,
                     notional=100.0)
    assert seen["pnl_pct"] > 0, "a net-profitable trade must not grade as a loss"
    # ...and the old basis is what it must NOT be
    assert seen["pnl_pct"] != -0.01


def test_no_notional_degrades_to_price_only_rather_than_inventing_one(monkeypatch):
    """A position restored from a pre-(sb) payload carries no notional. It must
    fall back to the price basis, NOT be re-based off the CURRENT clip — which
    may not be the clip it was opened at (the allocation scale rewrites
    order_usd mid-life). I8: unknown degrades to the old honest value, never to
    a guess."""
    seen = _capture(monkeypatch)
    fs._record_close("b", "ETH", 100.0, 1, 110.0, 999.0, True, "tp", True)
    assert seen["pnl_pct"] == 0.10, "must be the price return, not 999/clip"


def test_the_notional_is_stamped_at_entry_not_read_at_close():
    """`order_usd` is rewritten by the allocation scale at the top of the loop,
    so the clip in force at CLOSE is not the clip the leg was opened at. The
    open_notional() doctrine, applied to grading."""
    src = (ROOT / "lighter_funding_spread_bot.py").read_text()
    assert '"notional": float(order_usd),' in src, (
        "the position must record its OWN notional at entry")
    assert 'notional=m.get("notional")' in src, (
        "the close must use the position's stamped notional")


def test_it_changes_no_trade():
    """Restrict-direction proof: this pass touched grading only. If a future
    edit lets the notional reach an entry, exit or size decision, this fails."""
    src = (ROOT / "lighter_funding_spread_bot.py").read_text()
    body = src[src.index("def _record_close"):]
    body = body[:body.index("\ndef ")] if "\ndef " in body else body
    for forbidden in ("broker.open", "broker.close", "market_open", "order_usd ="):
        assert forbidden not in body, (
            f"_record_close must remain a recorder, not an actuator: {forbidden}")
