"""[(yj)] A ROSTER TYPED BY HAND GOES STALE ONE BOOK AT A TIME.

Four of them were stale at once, and each was found by reading the living feed
rather than the file:

  * `fleet_risk.FREQTRADE_BOTS` had no 🔭 georgia v3 — minted at `(vr)`,
    publishing, long-only, up to 5 slots — so her longs counted against
    NEITHER the enforced fleet long budget nor the shadow one, and her equity
    sat outside the 7d drawdown governor's cohort. A risk control that cannot
    see a book cannot restrain it.
  * `pnl_dashboard`'s bot_state position query named the bare
    `perps-funding-carry`, a row retired on 17-Jul; 🌾 carry publishes its
    state under `perps-funding-carry-lshadow`, so the card panel whose only
    source is that query has been empty for the fleet's best-evidenced book
    ever since.
  * `fleet_manifest.DESIGN` was missing 👩 mum's LIVE arm and 🔭 georgia v3
    (see `test_fleet_manifest.py` — its coverage guard was skipping).
  * `audit_lever_measurability.retired_rows` read 68 retired rows where 46
    are declared (see `test_lever_measurability_parse.py`).

The living roster is `tests/fixtures/living_rows.json`, committed so these
assertions can never degrade into a skip.
"""
import json
import pathlib

import pytest

pytestmark = pytest.mark.autonomy

import fleet_risk                                                # noqa: E402

SNAPSHOT = (pathlib.Path(__file__).resolve().parents[1]
            / "fixtures" / "living_rows.json")


def _living():
    return json.loads(SNAPSHOT.read_text())["rows"]


def _base(row):
    for suf in ("-lighter", "-lshadow", "-ltest"):
        if row.endswith(suf):
            return row[: -len(suf)]
    return row


def test_every_living_freqtrade_book_is_in_the_risk_roster():
    """Mutation: drop `freqtrade-georgia-v3` from FREQTRADE_BOTS => red.

    A `freqtrade-*` row is a family book and every family book holds
    directional positions the long budget is meant to bound. If one is absent
    from the roster its positions are counted nowhere — the failure is silent
    and it under-restricts, which is the wrong direction for a risk control."""
    roster = set(fleet_risk.FREQTRADE_BOTS) | set(fleet_risk.PERPS_LS_BOTS)
    missing = sorted({_base(r) for r in _living()
                      if r.startswith("freqtrade-")} - roster)
    assert not missing, (
        f"living family books outside fleet_risk's roster: {missing} — their "
        f"longs count against no budget and their equity against no governor")


def test_the_roster_resolves_every_name_it_carries_or_says_why():
    """A roster entry that resolves to nothing is the mirror defect: it reads
    as coverage and contributes zero. Retired names are legitimate (their rows
    are pruned), so this asserts the LIVING half only."""
    living_bases = {_base(r) for r in _living()}
    covered = [n for n in fleet_risk.FREQTRADE_BOTS if n in living_bases]
    assert len(covered) >= 4, covered


def test_the_state_position_rows_are_resolved_ids_not_bases():
    """`pnl_dashboard.STATE_POSITION_ROWS` — mutation: put the bare
    `perps-funding-carry` back => red. A funding book writes `bot_state` under
    the id it publishes its row under; the bare base has not existed since the
    17-Jul venue cut, and the query silently matched nothing for weeks."""
    src = (pathlib.Path(__file__).resolve().parents[2]
           / "pnl_dashboard.py").read_text()
    import ast
    tree = ast.parse(src)
    decl = next((n for n in tree.body if isinstance(n, ast.Assign)
                 and any(getattr(t, "id", None) == "STATE_POSITION_ROWS"
                         for t in n.targets)), None)
    assert decl is not None, "STATE_POSITION_ROWS is gone"
    rows = [e.value for e in decl.value.elts]
    living = set(_living())
    named_living = [r for r in rows if _base(r) in {_base(x) for x in living}]
    assert named_living, "the query names no living row at all"
    for r in named_living:
        assert r in living, (
            f"{r!r} is a BASE, not a published row id — "
            f"the query will match nothing")
