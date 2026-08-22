"""[2026-08-22 (sw)] The two studies (su)/(sv) rest on must stay runnable.

`SELFTEST_MODULES` cannot carry either: both filenames end in a hyphenated
date, so `"scripts.study_georgia_entry_rank_2026-08-22"` is not an importable
module name — an entry there collects ZERO tests and reports green, the trap
this repo already documented at `study_dislocation_band_2026-08-19` ((po): a
check that inspects nothing reports clean). Loading by PATH is the form that
actually runs them, and this file is the (sb) precedent applied again.

WHY GUARDED AT ALL — each carries a decision that was ACTED ON:

  * `study_farmer_gate_minvol_2026-08-22` is why 💸 the Farmer's entry gate was
    NOT moved. It replays the population the live book can actually trade
    (`MIN_VOL` $10M, which only 11 of 212 markets clear) instead of the top-N
    by rank the harness had always used — and that distinction inverts the
    verdict. Without it the sweep says gate 0.40, `+$14.95`, both halves
    positive; with it the SHIPPED 0.05 is the best of seven. A study that
    stops running takes a real-money refusal with it.
  * `study_georgia_entry_rank_2026-08-22` is why 🔮 georgia's throttle went
    2 -> 3. Its six controls are the whole basis for that change, and the next
    step (3 -> 4) is explicitly gated on re-running it against `entry_rank`
    rows rather than its own reconstruction.

Both `--selftest`s are offline and pure — no network, no cached tape, no DB —
so there is no reason to exempt them from being run, only from being IMPORTED
by dotted name.
"""
import importlib.util
import os

import pytest

_SCRIPTS = os.path.join(os.path.dirname(__file__), "..", "..", "scripts")
_STUDIES = {
    "farmer_gate_minvol": "study_farmer_gate_minvol_2026-08-22.py",
    "georgia_entry_rank": "study_georgia_entry_rank_2026-08-22.py",
}


def _load(name):
    path = os.path.join(_SCRIPTS, _STUDIES[name])
    spec = importlib.util.spec_from_file_location(f"_study_{name}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("name", sorted(_STUDIES))
def test_the_study_file_exists(name):
    assert os.path.exists(os.path.join(_SCRIPTS, _STUDIES[name])), (
        f"{_STUDIES[name]} is missing — the decision it carries is now "
        f"unreproducible")


@pytest.mark.parametrize("name", sorted(_STUDIES))
def test_selftest_passes(name):
    _load(name)._selftest()


def test_the_farmer_study_still_replays_the_books_own_population():
    """The ONE thing that made (su)'s verdict differ from every previous run of
    that harness: an absolute volume floor, not a rank. If `minvol_entry_ok`
    stops refusing an unknown volume, a data gap becomes a free pass and the
    replay drifts back toward the population the live book refuses."""
    m = _load("farmer_gate_minvol")
    mk = {"A": {"vol": {}},
          "B": {"vol": {h * 3600: 1e6 for h in range(100)}}}
    ok = m.minvol_entry_ok(mk, 10e6)
    assert ok("A", 50 * 3600) is False, "unknown volume must REFUSE, not pass"
    assert ok("B", 50 * 3600) is True


def test_the_georgia_study_prefers_the_stamp_over_its_own_reconstruction():
    """(sv) decided 2 -> 3 by reconstructing the rank from open timestamps and
    shipped `entry_rank` so the NEXT decision would not have to. If the study
    stops reading the stamp, the I23 fix it motivated is inert."""
    m = _load("georgia_entry_rank")
    rows, _ = m.rank_rows([
        {"opened_at": "2026-08-01T10:00:00+00:00", "pnl_pct": 0.01,
         "pnl_abs": 1.0, "reason": "long-x_roi", "extra": {"entry_rank": 9}}])
    assert rows[0]["stamped"] == 9, "the study ignores the stamped rank"
    assert rows[0]["rank"] == 1, "the reconstruction must still be available"
