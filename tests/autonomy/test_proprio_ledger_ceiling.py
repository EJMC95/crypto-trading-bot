"""[(aal)] `counts.episodes` was a CEILING wearing a count's clothes.

MEASURED 10-Sep: the episode ledger published `episodes: 120` — exactly
`EP_CAP` — and had been pinned there for the whole 24h bus history while
`graded` moved 88 -> 89 and `open` cycled 3 <-> 4. A number that a system
satisfies STRUCTURALLY is not a measurement (I7): `120` was byte-identical
between "we have 120 episodes" and "we are full and evicting".

The trajectory is why it matters rather than being a tidiness note. `(hl)` made
GRADED rows hold the budget first — correctly, since they are the only rows
`lever_verdicts` can use, and those verdicts steer the growth rail. At 89 of 120
growing ~1/day, `room` reaches zero in about a month; past that, ungraded rows
are dropped entirely and the oldest GRADED rows begin evicting each other, so
the verdicts would start turning over with nothing saying so.
"""
import pytest

import fleet_proprioception as FP

pytestmark = pytest.mark.autonomy


def _ep(i, status, end):
    return {"group": "g%d" % i, "status": status, "end": float(end),
            "stance": {}, "hours": 1.0, "reason": "x"}


#: THE REAL RULE, not a copy of it. The first cut of this file re-implemented
#: the trim inline and would have stayed green through any change to the module
#: — a second copy of a rule is a second rule ((hj)), which is why
#: `trim_episodes` was hoisted out of the build to be called from both sides.
_trim = FP.trim_episodes


def test_the_cap_is_published_beside_the_count():
    """Otherwise the reader cannot tell a full ledger from a busy one."""
    src = open(FP.__file__).read()
    assert '"ep_cap": EP_CAP,' in src
    assert '"room": _room,' in src and '"evicted": _evicted,' in src


def test_a_saturated_ledger_reports_room_zero_and_what_it_dropped():
    eps = ([_ep(i, "graded", i) for i in range(FP.EP_CAP + 5)]
           + [_ep(900 + i, "recorded", 900 + i) for i in range(7)])
    kept, room, evicted = _trim(eps)
    assert len(kept) == FP.EP_CAP
    assert room == 0, "graded alone fills the budget"
    assert evicted["graded"] == 5 and evicted["recorded"] == 7, evicted


def test_an_unsaturated_ledger_evicts_nothing_and_shows_its_room():
    eps = ([_ep(i, "graded", i) for i in range(10)]
           + [_ep(900 + i, "recorded", 900 + i) for i in range(3)])
    kept, room, evicted = _trim(eps)
    assert room == FP.EP_CAP - 10 and evicted == {"graded": 0, "recorded": 0}
    assert len(kept) == 13, "nothing dropped while there is room"


def test_graded_rows_still_hold_the_budget_first():
    """(hl)'s rule, re-pinned because this change touches its trim: a burst of
    ungradeable rows must never evict a graded one — graded rows are the only
    ones `lever_verdicts` can use, including the live-lane rows whose verdicts
    revert a real-money lever."""
    eps = ([_ep(i, "graded", i) for i in range(30)]
           + [_ep(900 + i, "recorded", 900 + i) for i in range(500)])
    kept, room, evicted = _trim(eps)
    assert sum(1 for e in kept if e["status"] == "graded") == 30, \
        "every graded row survives a flood of ungraded ones"
    assert evicted["graded"] == 0 and evicted["recorded"] == 500 - room


def test_the_counts_the_organ_publishes_are_the_ones_the_trim_computed():
    """Drive the real builder, not a fixture that 'looks like' the payload."""
    import inspect
    src = inspect.getsource(FP)
    assert "def trim_episodes(" in src, "the trim must have exactly one owner"
    i_call = src.index("episodes, _room, _evicted = trim_episodes(episodes)")
    i_counts = src.index('"ep_cap": EP_CAP')
    assert i_call < i_counts, "the eviction must be measured BEFORE it is published"
    # and the build must not carry its own copy of the trim
    assert src.count("[-EP_CAP:]") == 1, "only trim_episodes may apply the cap"
