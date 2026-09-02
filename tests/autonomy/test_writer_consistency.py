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

from scripts.audit_writer_consistency import (  # noqa: E402
    ORPHAN_H, classify, classify_orphan,
)


def test_the_2026_09_02_incident_is_a_finding():
    """The real numbers, WITH the ordering that makes them a finding: the
    orphan's build first traded 28-Aug, HEAD's 30-Aug. If this ever stops
    firing, the guard is decorative."""
    verdict, detail = classify("edc3032d1c46", 15, "4d93497e56d5", 15, 56, 9,
                               row_build_first_seen="2026-08-28",
                               trade_build_first_seen="2026-08-30")
    assert verdict == "SPLIT-BRAIN"
    assert "SUPERSEDED" in detail


def test_a_deploy_wave_is_not_a_split_brain():
    """[second live run] An hour after a fleet-wide deploy the first version
    printed 15 findings, 11 of them rows carrying the NEW build over trades
    still stamped with the OLD one. Direction is the whole test: a row whose
    build is newer than — or not yet seen among — the book's trades is
    REDEPLOY-LAG, reported only, never a finding."""
    # new build not yet seen trading (the first minutes after a deploy)
    v, d = classify("0af4038a63ba", 17, "4690a497e564", 17, 20, 20,
                    row_build_first_seen=None,
                    trade_build_first_seen="2026-08-30")
    assert v == "REDEPLOY-LAG", (v, d)
    # new build already trading, row simply predates the book's next close
    v, _ = classify("0af4038a63ba", 17, "4690a497e564", 17, 20, 20,
                    row_build_first_seen="2026-09-02",
                    trade_build_first_seen="2026-08-30")
    assert v == "REDEPLOY-LAG", v


def test_an_unorderable_difference_is_a_lead_not_a_finding():
    """I6: with no first-seen data on either side the difference cannot be
    ordered, and an absence is evidence only against a control group."""
    assert classify("aaa", 15, "bbb", 15, 10, 10)[0] == "AMBIGUOUS"


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
    """I6: the same inputs that flag a split brain must return OK when the
    stamps agree, or 'everything is flagged' and the finding means nothing."""
    assert classify("aaa", 15, "bbb", 15, 10, 10,
                    row_build_first_seen="2026-08-01",
                    trade_build_first_seen="2026-08-15")[0] == "SPLIT-BRAIN"
    assert classify("aaa", 15, "aaa", 15, 10, 10)[0] == "OK"


def test_a_trading_book_with_no_row_is_orphaned():
    """🔭 georgia-v3's shape, and the half a mutation proved untested: 41 closes,
    newest 0.4h ago, no bot_pnl row. If this stops firing, a book can trade into
    a row nothing publishes and no organ will ever enumerate it."""
    verdict, detail = classify_orphan(0.4, 41)
    assert verdict == "ORPHAN-BOOK"
    assert "NO bot_pnl row" in detail


def test_a_retired_book_is_never_orphaned():
    """A retired book keeps its ledger forever. Flagging it would redden this
    guard on every retirement the fleet has made — the cry-wolf failure that
    gets a detector ignored ((gl)). The clock is what separates them."""
    assert classify_orphan(ORPHAN_H + 1, 500)[0] is None
    assert classify_orphan(670.9, 189)[0] is None   # 🧲 Snap Back, retired 4-Aug


def test_orphan_needs_an_actual_ledger():
    """No closes, or no timestamp, is not an orphan — it is nothing to say."""
    assert classify_orphan(None, 0)[0] is None
    assert classify_orphan(1.0, 0)[0] is None
    assert classify_orphan(None, 10)[0] is None


def test_the_orphan_clock_is_the_discriminator():
    """Same book, same ledger, either side of the bar — the control that proves
    the clock is doing the work and not the close count."""
    assert classify_orphan(ORPHAN_H - 0.1, 41)[0] == "ORPHAN-BOOK"
    assert classify_orphan(ORPHAN_H + 0.1, 41)[0] is None


def test_the_audit_call_site_passes_the_first_seen_ordering():
    """Wiring, by AST — the (wi)-session lesson repeated: classify's direction
    logic is only as real as the call site that feeds it. Strip the first_seen
    kwargs and every difference degrades to AMBIGUOUS: no finding can ever
    fire and the guard is vacuous while every test above stays green."""
    import ast
    src = open(os.path.join(os.path.dirname(__file__), "..", "..",
                            "scripts", "audit_writer_consistency.py")).read()
    calls = [n for n in ast.walk(ast.parse(src))
             if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Name) and n.func.id == "classify"]
    def _live_value(call, name):
        for k in call.keywords:
            if k.arg == name:
                # a Constant (None included) is the mutation that survived the
                # first round: kwarg present, ordering dead. The value must be
                # a lookup into the first_seen map, not a literal.
                return (not isinstance(k.value, ast.Constant)
                        and "first_seen" in ast.unparse(k.value))
        return False
    wired = [c for c in calls
             if _live_value(c, "row_build_first_seen")
             and _live_value(c, "trade_build_first_seen")]
    assert wired, "no classify() call passes a LIVE first-seen ordering — " \
                  "every verdict degrades to AMBIGUOUS and nothing can fire"
