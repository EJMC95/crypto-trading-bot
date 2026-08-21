"""[(ne), 15-Aug] The avo-shadow capacity step, and the live surface it must
never touch.

The X3 throughput audit measured (adversarially confirmed, two referees):
avo shadow's cap-4 is BINDING — 39% of its era at 4/4, blocked SwingDip
signals during measured full windows — and cap 6 recovers ~+25% close rate
with NO era reset ((hc) capacity class). The referee's kill-class finding:
`lighter_avo_live_bot` binds the SAME SwingDip instance by identity and
sizes its REAL-MONEY clip as equity/max_open, so the STRATEGIES literal is
live surface. The step therefore ships as a SHADOW-runner env override
applied in main() only. These tests pin both halves.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import lighter_family_bot as fam  # noqa: E402


def test_the_declared_avo_literal_is_live_surface_and_stays_5():
    """The live bot divides real equity by this number. A casual literal
    edit here would add live slots and shrink the live clip on a real
    account — the exact (ne) kill-class. The shadow step rides the env
    override, never this line.

    [21-Aug (sr)] PIN MOVED 4 -> 5, deliberately and with the measurement in
    the registry comment: both arms are SIGNAL-limited (avg 2.24/2.41
    concurrent), the live arm sits at its ceiling 21.7% of the time, and the
    shadow reached 5 but never 6 in 17 episodes. The guard's PURPOSE is
    unchanged — it still fails an unexplained edit, which is what makes moving
    it a decision somebody has to justify rather than a diff nobody notices."""
    avo = [s for s in fam.STRATEGIES if s.bot == "freqtrade-avo-maria"]
    assert len(avo) == 1
    assert avo[0].max_open == 5, (
        "the SwingDip avo literal moved — that is LIVE clip geometry "
        "(equity * gross_x / max_open); shadow capacity belongs to "
        "FAMILY_SHADOW_MAX_OPEN_OVERRIDES, applied in main() only")


def test_import_does_not_apply_the_override():
    """The override is a main()-path act. At import, every instance carries
    its declared literal regardless of env — the live bot imports this
    module and must see untouched geometry even if the var leaks onto its
    service."""
    for s in fam.STRATEGIES:
        if s.bot == "freqtrade-avo-maria":
            assert s.max_open == 5


def test_override_parser_defaults_to_the_measured_avo_step():
    got = fam.shadow_max_open_overrides()
    assert got.get("freqtrade-avo-maria") == 6, got


def test_override_parser_is_revertible_and_junk_safe():
    assert fam.shadow_max_open_overrides("") == {}
    assert fam.shadow_max_open_overrides("freqtrade-avo-maria:8") == {
        "freqtrade-avo-maria": 8}
    # clamps, junk dropped never guessed
    assert fam.shadow_max_open_overrides("a:99,b:junk,c") == {"a": 12}
    assert fam.shadow_max_open_overrides("x:0") == {"x": 1}
