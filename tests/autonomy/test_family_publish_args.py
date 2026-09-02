"""[2026-09-02] A PUBLISH THAT CANNOT BE BUILT IS A ROW GOING SILENTLY STALE.

The incident this closes: (vr)'s `spend_extra` read `b.bot` on a Book whose
attribute is `bot_id`, so building the publish's `extra` raised
AttributeError for EVERY family book on EVERY loop — inside the publish
site's `except: pass`. For five days no post-(vr) container could publish a
single family row; the fleet looked healthy only because a STALE Railway
instance running pre-(vr) code kept writing mum/avo/georgia-v1 (build stamp
`edc3032d1c46` = d2c0cb9, 28-Aug 21:09), and 🔮 georgia-v3 — absent from
that old roster — never got a row at all, which also blinded
`audit_book_spend` (it reads the feed; a missing row is invisible to the
auditor built for it).

The class-closing shape: `family_publish_extra` is the ONE builder of the
published extra, and this test drives it for EVERY live strategy against a
REAL Book — publisher-built, never a hand-shaped fixture ((hj)). A builder
that raises for any book, present or future, reddens here instead of a row
going quietly dark.
"""
import ast
import inspect
import json
import os
import sys
import time

import pytest

pytestmark = pytest.mark.autonomy

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("VENUE", "lighter_shadow")

import lighter_family_bot as fam                     # noqa: E402


def _books():
    out = []
    for s in fam.live_strategies():
        coins = list(getattr(s, "coins", []) or ["BTC"])[:3]
        out.append(fam.Book(s, "lighter_shadow", coins))
    return out


def test_every_live_books_publish_extra_builds_and_is_json_safe():
    books = _books()
    assert len(books) >= 2, "roster collapsed — this test lost its subjects"
    t0 = time.time()
    for b in books:
        extra = fam.family_publish_extra(b, "lighter_shadow", True, t0)
        # the (vr) failure was a RAISE; the floor here is "builds, and the
        # store could write it" — json round-trip with NaN refused (I5)
        json.dumps(extra, allow_nan=False)
        assert extra.get("family") is True and extra.get("style"), b.bot_id


def test_v3_publishes_her_spend_census_and_the_elders_stay_grandfathered():
    """The very field whose builder broke everything: v3 is the one
    BOOK_BORN_TS member, so her extra must carry `spend` (I22 — she was born
    after the bar) while the grandfathered books keep their {} exactly."""
    t0 = time.time()
    by_bot = {b.s.bot: fam.family_publish_extra(b, "lighter_shadow", True, t0)
              for b in _books()}
    if "freqtrade-georgia-v3" in by_bot:            # she may retire on 10-Sep
        sp = by_bot["freqtrade-georgia-v3"].get("spend")
        assert sp, "v3 lost her I22 spend census — the (vr) intent, unbroken"
        assert sp.get("markets_scanned") and sp.get("n_eff") == 1.0
    for bot in ("freqtrade-mum", "freqtrade-avo-maria"):
        assert "spend" not in by_bot[bot], (
            f"{bot} grew a spend census — grandfathered per spend_extra's "
            "own doc; audit_book_spend must drive that change, not a drift")


def test_the_publish_site_uses_the_one_builder_and_logs_its_failure():
    """Wiring by AST, not substring: the loop's publish must build `extra`
    via family_publish_extra (args inside its try are what made the (vr)
    raise silent), and the except clause must not be a bare `pass` — five
    days of a persistent condition with zero log lines is the I4 shape."""
    src = inspect.getsource(fam.main)
    calls = [n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Call)
             and getattr(n.func, "id", "") == "family_publish_extra"]
    assert calls, "main() no longer builds extra through family_publish_extra"
    assert "publish FAILED" in src, (
        "the publish except went silent again — a failed publish must say so")
