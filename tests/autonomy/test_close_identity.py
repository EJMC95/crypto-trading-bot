"""The ':None' collision class — one owner, both halves, mutation-pinned.

[2026-08-27] `f"{pair}:{m.get('opened_ts')}"` rendered a missing open time as
the literal "None", so every unknown-open close on one pair shared a primary
key — and paper_trades upserts ON CONFLICT DO UPDATE, so the second one
OVERWROTE the first, pnl included. 15 exposed rows on the two real-money
books; one (georgia LIT, -$0.84, entry 3.6604) is a REAL trade.

The same None fabricated the open STAMP from the current loop clock, which
runs after the close instant -> 8 rows with opened_at LATER than closed_at.
"""
from datetime import datetime, timezone

import pytest

from lighter_family_bot import close_identity


def _t(epoch):
    return datetime.fromtimestamp(epoch, tz=timezone.utc)


# --------------------------------------------------------------- known open
def test_known_open_id_is_byte_identical_to_the_shipped_format():
    """LOAD-BEARING: the upsert MATCHES on trade_id. A changed format turns
    every re-published close into a duplicate INSERT and double-counts a live
    book's ledger. Pinned against a REAL id read from the ledger."""
    opened = 1787808646.8214896
    tid, _ = close_identity("DOT", opened, _t(1787812000.0))
    assert tid == "DOT:1787808646.8214896"
    assert tid == f"DOT:{opened}"


def test_known_open_stamp_is_the_open_not_the_close():
    _, opened_iso = close_identity("DOT", 1787808646.0, _t(1787812000.0))
    assert opened_iso == _t(1787808646.0).isoformat()


def test_known_open_never_takes_the_event_path():
    tid, _ = close_identity("ETH", 1787808646.0, _t(1787812000.0))
    assert ":evt:" not in tid


# ------------------------------------------------------------- unknown open
@pytest.mark.parametrize("unknown", [None, 0, 0.0])
def test_unknown_open_never_renders_the_none_literal(unknown):
    """The whole defect: 'None' (or '0') as an id component is a shared key."""
    tid, _ = close_identity("LIT", unknown, _t(1787812000.0))
    assert tid.endswith(":evt:1787812000.000")
    assert "None" not in tid
    assert tid != "LIT:None"


def test_two_unknown_open_closes_on_one_pair_get_DIFFERENT_ids():
    """THE REGRESSION THAT MATTERS. Same pair, two halt events -> under the
    old rule both were 'LIT:None' and the second overwrote the first."""
    a, _ = close_identity("LIT", None, _t(1787812000.0))
    b, _ = close_identity("LIT", None, _t(1787812300.0))
    assert a != b, "two unknown-open closes must not share a primary key"


def test_unknown_open_stamp_never_postdates_the_close():
    """8 live rows carried opened_at AFTER closed_at because the fallback was
    time.time() — a later clock than the close computed earlier in the pass."""
    close = _t(1787812000.0)
    _, opened_iso = close_identity("ZEC", None, close)
    assert datetime.fromisoformat(opened_iso) <= close
    assert opened_iso == close.isoformat()


def test_unknown_open_cannot_collide_with_a_real_trade_id():
    """A real trade is '<pair>:<epoch>'; an event must not be able to land on
    one by construction, whatever the clock reads."""
    real, _ = close_identity("LIT", 1787812000.0, _t(1787812500.0))
    evt, _ = close_identity("LIT", None, _t(1787812000.0))
    assert real != evt


# ------------------------------------------------------- one owner (I/(hj))
def test_neither_write_site_builds_trade_id_from_an_f_string():
    """AST-shaped WIRING test, narrowed to the ONE defect shape: a
    `trade_id=f"..."` keyword at a publish_paper_trade call. That is the
    collision form — the id must come from close_identity(), which is the
    only place allowed to decide what an unknown open renders as.

    Deliberately NOT a substring scan: `close_identity` legitimately builds
    an f-string internally, and a page-wide grep cannot tell the owner from a
    caller re-implementing it ((hj) / a-substring-test-is-not-a-wiring-test).
    """
    import ast
    import pathlib
    checked = 0
    for mod in ("lighter_family_bot.py", "lighter_avo_live_bot.py"):
        src = pathlib.Path(mod).read_text()
        assert "close_identity(" in src, f"{mod} must call the owner"
        for node in ast.walk(ast.parse(src)):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            name = getattr(fn, "attr", None) or getattr(fn, "id", None)
            if name != "publish_paper_trade":
                continue
            checked += 1
            for kw in node.keywords:
                if kw.arg != "trade_id":
                    continue
                assert not isinstance(kw.value, ast.JoinedStr), (
                    f"{mod}: trade_id built from an f-string at a publish "
                    "site is the ':None' collision form — pass the id from "
                    "close_identity() instead")
    assert checked >= 2, (
        f"expected both carrier publish sites, saw {checked} — the test "
        "found nothing to check, which is not a pass")


def test_the_wiring_test_can_actually_fire():
    """A check that inspects nothing reports clean, and clean reads as
    evidence. Prove the matcher fires on the exact pre-fix source."""
    import ast
    bad = ast.parse(
        'store.publish_paper_trade(BOT, trade_id=f"{sym}:{m.get(1)}")')
    hits = [kw for n in ast.walk(bad) if isinstance(n, ast.Call)
            and getattr(n.func, "attr", None) == "publish_paper_trade"
            for kw in n.keywords
            if kw.arg == "trade_id" and isinstance(kw.value, ast.JoinedStr)]
    assert len(hits) == 1, "the matcher must catch the pre-fix form"
