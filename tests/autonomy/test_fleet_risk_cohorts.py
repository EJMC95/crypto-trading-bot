"""[2026-09-02 (wp)] PAPER POSITIONS WERE VETOING REAL MONEY, AND REAL MONEY
WAS VETOING PAPER — one long budget for two kinds of book.

MEASURED ON THE LIVE BUS, 2-Sep: the pooled `long_positions` sat AT the
20-long budget in 17 of 285 five-minute samples (6.0% of the day, every one
since 02:02Z), composed of 👩 mum 11 (real) + 🙏 avo 3 (real) + 🎫 the shadow
taker 6 (PAPER). Both real-money rows published `fleet_long_veto: true` with
slots free (mum 11 of 12, avo 3 of 5). A paper position carries no risk to a
real-money book, and a real one carries none to a paper book — so a single
count is a category error in both directions, and the shadow twin of a live
base (freqtrade-mum-lshadow) was counted NOWHERE because `authoritative_row`
resolves the base to its live row.

THE FIX: fleet_risk publishes `cohorts.{live,shadow}.{long_positions,
long_budget}` beside the unchanged pooled pair; fleet_bus.cohort_long_state
is the ONE reader; every veto consumer asks for its own cohort and degrades to
the pooled pair when the key is absent (an old-shape payload must veto exactly
as before — never nothing, never on the other cohort's number).

Mutations that turn these red: drop the `-lshadow` twin pass in cohort_longs;
make cohort_long_state ignore `cohorts`; make the fallback return (0, 10**9);
count a `lighter_live` row into `shadow`.
"""
import ast
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

import fleet_bus as fb    # noqa: E402
import fleet_risk as fr   # noqa: E402

pytestmark = pytest.mark.autonomy


from datetime import datetime, timedelta, timezone  # noqa: E402


def _row(bot, held=None, open_pos=None, age=30):
    n = len(held or {}) + len(open_pos or [])
    upd = (datetime.now(timezone.utc) - timedelta(seconds=age)).isoformat()
    return {"bot": bot, "age_sec": age, "status": "online",
            "updated_at": upd, "open_trades": n,
            "extra": {**({"held": held} if held else {}),
                      **({"open_pos": open_pos} if open_pos else {})}}


def _by_bot(rows):
    return {r["bot"]: r for r in rows}


def test_the_two_september_live_books_and_the_paper_taker_split_by_venue():
    """The measured 2-Sep state: 11 + 3 real, 6 paper -> live 14, shadow 6.
    Pooled stays 20, so the light and dashboard are untouched."""
    bb = _by_bot([
        _row("freqtrade-mum-lighter", held={c: "oversold" for c in
                                            "ABCDEFGHIJK"}),
        _row("freqtrade-avo-maria-lighter", held={"TAO": "x", "TRX": "x",
                                                  "XCU": "x"}),
        _row("lighter-ticket-taker-lshadow",
             open_pos=[{"pair": f"S{i}/USDC", "tag": "long-breakoutup"}
                       for i in range(6)]),
    ])
    c = fr.cohort_longs(bb, ["freqtrade-mum", "freqtrade-avo-maria",
                             "lighter-ticket-taker"], [])
    assert c == {"live": 14, "shadow": 6}, c


def test_a_live_bases_shadow_twin_is_counted_in_the_shadow_cohort():
    """The population the pooled loop structurally cannot see: mum's paper
    twin. Mutation: delete the `+ "-lshadow"` twin pass."""
    bb = _by_bot([
        _row("freqtrade-mum-lighter", held={"A": "x", "B": "x"}),
        _row("freqtrade-mum-lshadow", held={"C": "x", "D": "x", "E": "x"}),
    ])
    c = fr.cohort_longs(bb, ["freqtrade-mum"], [])
    assert c == {"live": 2, "shadow": 3}, c
    # a STALE twin is a corpse, not a position (I1)
    bb["freqtrade-mum-lshadow"]["updated_at"] = (
        datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    assert fr.cohort_longs(bb, ["freqtrade-mum"], [])["shadow"] == 0


def test_shorts_are_not_longs_in_either_cohort():
    bb = _by_bot([
        _row("lighter-ticket-taker-lshadow",
             open_pos=[{"pair": "A/USDC", "tag": "short-divergence"},
                       {"pair": "B/USDC", "tag": "long-breakoutup"}]),
        _row("perps-funding-lighter-lshadow", held={"ETH": "S", "SOL": "L"}),
    ])
    c = fr.cohort_longs(bb, ["lighter-ticket-taker"], ["perps-funding-lighter"])
    assert c == {"live": 0, "shadow": 2}, c


def test_row_longs_is_the_same_rule_the_pooled_loop_applies():
    """open_pos tags rule when present, open_trades otherwise; perps rows
    read extra.longs first, then the held map's L side."""
    assert fr.row_longs({"open_trades": 4, "extra": {}}) == 4
    assert fr.row_longs({"open_trades": 2, "extra": {"open_pos": [
        {"tag": "short-x"}, {"tag": "long-y"}]}}) == 1
    assert fr.row_longs({"extra": {"longs": 3, "held": {"A": "S"}}}, "perps") == 3
    assert fr.row_longs({"extra": {"held": {"A": "S", "B": "L"}}}, "perps") == 1
    assert fr.row_longs(None) == 0


def test_cohort_long_state_prefers_the_cohort_and_degrades_to_the_pooled_pair():
    p = {"long_positions": 20, "long_budget": 20,
         "cohorts": {"live": {"long_positions": 14, "long_budget": 20},
                     "shadow": {"long_positions": 6, "long_budget": 20}}}
    assert fb.cohort_long_state(p, "live") == (14, 20)
    assert fb.cohort_long_state(p, "shadow") == (6, 20)
    # the 2-Sep reading: pooled says VETO, the live cohort says GO
    assert p["long_positions"] >= p["long_budget"]
    lp, lb = fb.cohort_long_state(p, "live")
    assert lp < lb
    # old-shape payload -> byte-identical to the pooled read
    old = {"long_positions": 20, "long_budget": 20}
    assert fb.cohort_long_state(old, "live") == (20, 20)
    assert fb.cohort_long_state(old, "shadow") == (20, 20)
    # a missing budget is NO veto (10**9), 0 is a REAL budget
    assert fb.cohort_long_state({"long_positions": 3}, "live") == (3, 10 ** 9)
    assert fb.cohort_long_state({"long_positions": 3, "long_budget": 0},
                                "live") == (3, 0)
    # junk cohort block -> pooled, never a crash
    assert fb.cohort_long_state({"long_positions": 1, "long_budget": 5,
                                 "cohorts": "junk"}, "live") == (1, 5)
    assert fb.cohort_long_state({"long_positions": 1, "long_budget": 5,
                                 "cohorts": {"live": {"long_positions": "x"}}},
                                "live") == (1, 5)


def test_long_entries_blocked_honours_the_cohort(monkeypatch):
    p = {"updated": fb.datetime.now(fb.timezone.utc).isoformat(),
         "ttl_sec": 900, "mode": "enforce",
         "long_positions": 20, "long_budget": 20,
         "cohorts": {"live": {"long_positions": 14, "long_budget": 20},
                     "shadow": {"long_positions": 6, "long_budget": 20}}}
    monkeypatch.setattr(fb, "_load", lambda key, ct=None: p)
    assert fb.long_entries_blocked() is True          # legacy pooled read
    assert fb.long_entries_blocked(cohort="live") is False
    assert fb.long_entries_blocked(cohort="shadow") is False
    p["cohorts"]["live"]["long_positions"] = 20
    assert fb.long_entries_blocked(cohort="live") is True


def test_venue_cohort_fails_toward_shadow():
    assert fr.venue_cohort("lighter_live") == "live"
    assert fr.venue_cohort("lighter_shadow") == "shadow"
    assert fr.venue_cohort(None) == "shadow"
    assert fr.venue_cohort("hl_paper") == "shadow"


_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.mark.parametrize("path,cohort_expr", [
    ("lighter_avo_live_bot.py", "live"),
    ("lighter_family_bot.py", "shadow"),
])
def test_every_veto_consumer_asks_for_a_cohort(path, cohort_expr):
    """AST: the live host asks for `live`, the family shadow host for
    `shadow`, and neither re-types the pooled read at the veto site.
    Mutation: put `fr.get("long_positions")` back at the veto."""
    src = Path(_ROOT, path).read_text()
    tree = ast.parse(src)
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
             and str(getattr(n.func, "attr", getattr(n.func, "id", "")))
             .endswith("cohort_long_state")]
    literals = {a.value for c in calls for a in c.args
                if isinstance(a, ast.Constant)}
    assert cohort_expr in literals, (path, literals)


def test_the_taker_and_funding_arms_pick_their_cohort_by_venue():
    for path in ("lighter_ticket_taker.py", "lighter_funding_bot.py"):
        src = Path(_ROOT, path).read_text()
        assert "cohort_long_state" in src, path
        assert '"live"' in src and '"shadow"' in src, path


def test_fleet_risk_publishes_the_cohort_block_beside_the_pooled_pair():
    src = Path(_ROOT, "fleet_risk.py").read_text()
    assert '"cohorts": {' in src and '"long_positions": fleet_long' in src
    assert fr.LIVE_LONG_BUDGET >= 0
