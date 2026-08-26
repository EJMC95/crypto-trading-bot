"""[(uc)] THE JOINT SWEEP WAS DARK FOR 4.5 DAYS OF EVERY ORBIT.

`explore_slice` walked CONTIGUOUS indices of the joint gene product, and the
in-cage (enactable) subspace is contiguous under the same mixed-radix odometer.
Measured on the shipped grids: 5,760 of 226,800 research genotypes are fully
in-cage (2.54%), every enactable index lies in [47167, 179883], and **107 of
152 cycles per orbit produced ZERO enactable genotypes**. Production's cursor
(68850) sat inside one of those dead stretches when this was found — so the
mechanism added to make gene INTERACTIONS reachable could not contribute a
gamete for ~4.5 days at a stretch.

The fix strides the walk by a step COPRIME to the space size. Coprimality is
the whole safety of it: a stride sharing a factor with `size` walks a SUBGROUP
and would make part of the space permanently unreachable — strictly worse than
the dead stretches. With gcd == 1 coverage is unchanged and only the ORDER
moves.

Each test names the property it pins, because a stride that quietly lost
coverage would look identical to one that fixed the problem.
"""
import math
import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent.parent
for _p in (str(REPO), str(REPO / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import strategy_incubator as si  # noqa: E402

pytestmark = pytest.mark.autonomy

#: a small joint space we can enumerate exhaustively (3*4*2 = 24)
SMALL = {"A": ("a", [1, 2, 3]), "B": ("b", [1, 2, 3, 4]), "C": ("c", [1, 2])}


def _live_genes():
    return si.RESEARCH_GENES if getattr(si, "RESEARCH_MODE", False) else si.TAKER_GENES


# ---------------------------------------------------------------------------
# 1. COPRIMALITY — the property that keeps coverage total
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("size", [3, 4, 5, 8, 12, 24, 97, 1500, 5760, 226800])
def test_the_stride_is_always_coprime_to_the_space(size):
    """A stride sharing a factor with `size` walks a SUBGROUP — part of the
    space becomes unreachable FOREVER, which is worse than the dead stretches
    this replaces. gcd == 1 is the only thing standing between the two."""
    s = si.explore_stride(size)
    assert 1 <= s <= size, f"stride {s} outside [1, {size}]"
    assert math.gcd(s, size) == 1, (
        f"stride {s} shares a factor with space {size} — the walk would visit "
        f"only {size // math.gcd(s, size)} of {size} indices, ever")


@pytest.mark.parametrize("size", [0, 1, 2])
def test_a_degenerate_space_degrades_to_one(size):
    """No space to stride through: step 1, never 0 (a 0 stride would return
    the same genotype forever and the cursor would never advance)."""
    assert si.explore_stride(size) == 1


# ---------------------------------------------------------------------------
# 2. FULL COVERAGE — driven exhaustively, not argued
# ---------------------------------------------------------------------------
def test_every_index_is_still_visited_exactly_once_per_period():
    """THE LOAD-BEARING TEST. Walk the whole small space one genotype at a
    time and require all 24 distinct — coverage is what the contiguous walk
    had and what a careless stride would silently destroy."""
    n = si.joint_space_size(SMALL)
    seen, cur = set(), 0
    for _ in range(n):
        pop, cur, size = si.explore_slice(SMALL, cur, 1)
        assert size == n
        seen.add(tuple(sorted(pop[0].items())))
    assert len(seen) == n, (
        f"strided walk visited {len(seen)} of {n} genotypes in a full period — "
        "coverage was lost, which is exactly what coprimality must prevent")


def test_the_walk_is_deterministic_across_processes():
    """The cursor must mean the same thing next hour as it did this hour —
    the stride is derived from `size` alone, so an unchanged gene set gives an
    unchanged sequence."""
    a, ca, _ = si.explore_slice(SMALL, 7, 5)
    b, cb, _ = si.explore_slice(SMALL, 7, 5)
    assert a == b and ca == cb


def test_a_slice_returns_no_duplicates_within_itself():
    """take <= size with a coprime stride cannot repeat; if dedupe ever has
    work to do here, the stride is wrong."""
    n = si.joint_space_size(SMALL)
    pop, _, _ = si.explore_slice(SMALL, 0, n)
    keys = [tuple(sorted(g.items())) for g in pop]
    assert len(keys) == len(set(keys)) == n


# ---------------------------------------------------------------------------
# 3. THE FIX ITSELF — non-vacuous, at production's own cursor
# ---------------------------------------------------------------------------
def _contiguous_slice(genes, cursor, n):
    """The PRE-FIX walk, kept here as the control. Without it this file could
    not show that the strided walk changed anything."""
    names = sorted(genes)
    grids = [genes[g][1] for g in names]
    size = si.joint_space_size(genes)
    start = int(cursor or 0) % size
    pop = []
    for k in range(min(n, size)):
        idx = (start + k) % size
        gt, rem = {}, idx
        for name, grid in zip(names, grids):
            gt[name] = grid[rem % len(grid)]
            rem //= len(grid)
        pop.append(gt)
    return pop


def test_the_live_cursor_stops_being_a_dead_stretch():
    """Production's cursor was 68850 and the contiguous walk yielded ZERO
    enactable genotypes there, cycle after cycle. This is the whole point of
    the change, so it is pinned at that exact cursor with a CONTROL — a test
    that only measured the strided walk could not tell a fix from a no-op."""
    genes = _live_genes()
    n = si.EXPLORE_N
    before = _contiguous_slice(genes, 68850, n)
    after, _, _ = si.explore_slice(genes, 68850, n)
    hits_before = sum(1 for gt in before if si.is_enactable(gt, genes))
    hits_after = sum(1 for gt in after if si.is_enactable(gt, genes))
    assert hits_before == 0, (
        "the pre-fix control no longer reproduces the dead stretch — the "
        "grids or the cage moved, so re-derive this test's premise")
    assert hits_after > 0, (
        "the strided walk still yields no enactable genotype at the cursor "
        "that motivated the fix")


def test_every_cycle_carries_in_cage_genotypes_not_just_the_lucky_one():
    """A stride that merely MOVED the dead stretch would pass the test above
    on one cursor and fail the organ. Require in-cage genotypes on every one
    of several consecutive cycles."""
    genes = _live_genes()
    cur, hits = 68850, []
    for _ in range(8):
        pop, cur, _ = si.explore_slice(genes, cur, si.EXPLORE_N)
        hits.append(sum(1 for gt in pop if si.is_enactable(gt, genes)))
    assert all(h > 0 for h in hits), (
        f"a cycle still yields zero enactable genotypes: {hits}")


def test_the_kill_switch_still_explores_nothing():
    """`n <= 0` is a clean kill switch and the stride must not resurrect it."""
    for n in (0, -1):
        pop, cur, size = si.explore_slice(_live_genes(), 123, n)
        assert pop == [] and cur == 123 and size > 0
