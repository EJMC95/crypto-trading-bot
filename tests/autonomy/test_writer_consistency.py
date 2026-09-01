"""[2026-09-02] Pins the SPLIT-BRAIN detector against the incident that made it.

The incident: `family-lighter-shadow` ran two code states at once for five days
and seven deploys. Trades carried `4d93497e56d5` (b638893..HEAD); the summary
rows carried `edc3032d1c46` (29135cd..d2c0cb9) — disjoint commit windows, so
one process could not have written both. 👩 mum's row reported 9 closes against
56 in her ledger; 🔭 georgia-v3 traded 41 closes with no row at all.

Three existing guards were green throughout (`audit_ledger_integrity` tests
position overlap; `audit_code_currency` compares container-to-repo;
`evidence_review`'s drift arm always defers on this image's 15-vs-16 file
count). This test pins the one comparison that could not be green: a book's own
row versus a book's own newest trade, both written through `_stamp_build` by the
same process.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.audit_writer_consistency import classify  # noqa: E402


def test_the_2026_09_02_incident_is_a_finding():
    """The real numbers. If this ever stops firing, the guard is decorative."""
    verdict, detail = classify("edc3032d1c46", 15, "4d93497e56d5", 15, 56, 9)
    assert verdict == "SPLIT-BRAIN"
    assert "two code states" in detail


def test_agreeing_stamps_are_never_a_finding():
    """One process stamps its row and its trades identically — always."""
    assert classify("abc", 15, "abc", 15, 56, 55)[0] == "OK"


def test_a_differing_file_count_alone_is_not_drift():
    """The (fd) trap is repo-vs-container. Row and ledger come from ONE
    process, so a differing `build_n` with the same id is bookkeeping, never a
    split brain — asserting otherwise would make this guard cry wolf on every
    image whose COPY set differs from the repo tree, which is what blinded
    `evidence_review`'s arm in the first place."""
    assert classify("abc", 15, "abc", 16, 10, 10)[0] == "OK"


def test_silence_is_not_a_split_brain():
    """A book with no closes in the window has no ledger side. Reporting that
    as a finding is the failure mode where a detector flags everything and the
    operator learns to ignore it ((gl))."""
    assert classify("abc", 15, None, None, 0, 0)[0] == "QUIET"


def test_an_unstamped_side_does_not_vote():
    """I6/I8: a sensor that cannot see must not vote, and it must not degrade
    to a guess in either direction."""
    assert classify(None, None, "abc", 15, 5, 5)[0] == "UNSTAMPED"
    assert classify("abc", 15, "", None, 5, 5)[0] == "UNSTAMPED"
    assert classify("abc", 15, None, 15, 5, 5)[0] == "QUIET"


def test_the_closes_gap_is_corroboration_and_can_never_create_a_finding():
    """The gap between a row's `closed_trades` and its ledger count is the
    symptom that made the incident legible — but a row legitimately lags its
    ledger by one publish cadence, so it is a NOTE on an already-agreeing pair
    and never a verdict of its own. If this inverts, the guard starts failing
    healthy books at every publish boundary."""
    verdict, detail = classify("abc", 15, "abc", 15, 56, 9)
    assert verdict == "OK"
    assert "large gap" in detail
    assert "large gap" not in classify("abc", 15, "abc", 15, 56, 55)[1]


def test_the_detector_has_a_control_group():
    """I6: the same call that flags a split brain must return OK for a healthy
    book, or 'everything is flagged' and the finding means nothing."""
    assert classify("aaa", 15, "bbb", 15, 10, 10)[0] == "SPLIT-BRAIN"
    assert classify("aaa", 15, "aaa", 15, 10, 10)[0] == "OK"
