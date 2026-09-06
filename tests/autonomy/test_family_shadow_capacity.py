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


def test_the_declared_avo_literal_is_live_surface_and_stays_6():
    """The live bot divides real equity by this number. A casual literal
    edit here would add live slots and shrink the live clip on a real
    account — the exact (ne) kill-class. The shadow step rides the env
    override, never this line.

    [21-Aug (sr)] PIN MOVED 4 -> 5, deliberately and with the measurement in
    the registry comment: both arms are SIGNAL-limited (avg 2.24/2.41
    concurrent), the live arm sits at its ceiling 21.7% of the time, and the
    shadow reached 5 but never 6 in 17 episodes. The guard's PURPOSE is
    unchanged — it still fails an unexplained edit, which is what makes moving
    it a decision somebody has to justify rather than a diff nobody notices.

    [6-Sep (ye)] PIN MOVED 5 -> 6, on the twin's own record — the (sr) premise
    "never 6" was false two weeks later: 6 held 8.3% of her life (peak 7), and
    the FOUR trades opened with >=5 already held earned +6.877%/trade (+$13.76,
    53% of her +$25.80) vs +1.027% for the other 28. Priced −14% deployed
    capital on the ordinary trades against 27.5 clip-% on the marginal ones.
    Both arms now read 6 (the shadow override default is EMPTY), so the judge's
    avo pair leaves `capacity_mismatch`. Pre-registered revert: session_state
    row `avo-live-slot-6-preregistered-read` (6-Oct). This guard still fails
    the NEXT unexplained edit — that is its whole job."""
    avo = [s for s in fam.STRATEGIES if s.bot == "freqtrade-avo-maria"]
    assert len(avo) == 1
    assert avo[0].max_open == 6, (
        "the SwingDip avo literal moved — that is LIVE clip geometry "
        "(equity * gross_x / max_open); a move needs its measurement here "
        "and in the literal's own comment, like (sr) and (ye)")


def test_import_does_not_apply_the_override():
    """The override is a main()-path act. At import, every instance carries
    its declared literal regardless of env — the live bot imports this
    module and must see untouched geometry even if the var leaks onto its
    service."""
    avo = next(s for s in fam.STRATEGIES if s.bot == "freqtrade-avo-maria")
    assert avo.max_open == 6              # the literal, at import
    # [(ye)] the default is empty now, so also prove the PARSER is pure: an
    # explicit raw string yields a map and mutates no instance.
    assert fam.shadow_max_open_overrides("freqtrade-avo-maria:9") == {
        "freqtrade-avo-maria": 9}
    assert avo.max_open == 6, "parsing an override must not touch the instance"


def test_override_default_is_empty_and_the_measured_step_lives_in_the_literal():
    """[(ye)] RE-AIMED (I26: a pin is not a reason). This asserted the default
    carried `freqtrade-avo-maria:6` — the (ne) shadow-only step. That step is
    now the LITERAL on both arms (the twin's 6th slot took its best trades,
    +6.877%/trade on the 4 marginal entries), so the resting default is EMPTY:
    a shadow-only override silently re-opens a cap delta between the arms,
    which is exactly what held the judge's avo pair at `capacity_mismatch`."""
    assert fam.shadow_max_open_overrides() == {}, "resting default must be empty"
    avo = next(s for s in fam.STRATEGIES if s.bot == "freqtrade-avo-maria")
    assert avo.max_open == 6, "the measured step lives in the literal now"


def test_override_parser_is_revertible_and_junk_safe():
    assert fam.shadow_max_open_overrides("") == {}
    assert fam.shadow_max_open_overrides("freqtrade-avo-maria:8") == {
        "freqtrade-avo-maria": 8}
    # clamps, junk dropped never guessed
    assert fam.shadow_max_open_overrides("a:99,b:junk,c") == {"a": 12}
    assert fam.shadow_max_open_overrides("x:0") == {"x": 1}
