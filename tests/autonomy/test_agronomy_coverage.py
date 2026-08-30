"""🌱 fleet_agronomy must be able to SEE every book the fleet still runs.

INCIDENT (2026-08-19). The organ whose whole question is "does this plant have
light and water" covered **10 of 18 living rows**. Eight books were invisible to
it — the entire BOOKS/BAND/NAV cohort born 13..19-Aug (band-garrett, band-kelly,
book-douglas, book-grimes, book-hull, book-kiyosaki, nav-cook) and, worst,
`freqtrade-avo-maria-lighter`, **a REAL-MONEY row**. Meanwhile it still carried a
spec for `lighter-ticket-taker-lighter`, the live arm 🙏 Avo REPLACED on 13-Aug
((ma)) — so the standing scan described a book that no longer trades and said
nothing about the one that does.

That is the `(ci)`/`(ma)` class ("a standing audit rule that names a retired bot
sends every future audit to check the wrong file") landing on the organ that is
supposed to notice when a book has no room to grow. Nothing failed; the scan
just quietly had a smaller world than the fleet.

WHY A TEST AND NOT A LONGER LIST: this repo's own rule — *"a list that must be
remembered is the control that already failed"*. `scripts/fleet_books.ROW_ENTRY`
is the maintained row→module registry (a new book is added there at birth so
`audit_code_currency` can resolve its stamp), so it is the honest reference to
diff against. Offline and deterministic: no network, no live feed.

A book may be absent from the organ ONLY as a DECLARED decision, with a reason —
the `BORN_DARK_OK` idiom.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import fleet_agronomy as agronomy  # noqa: E402
import fleet_books  # noqa: E402

#: Rows in ROW_ENTRY that agronomy deliberately does not spec, each with why.
#: RETIRED books keep their ROW_ENTRY mapping (stamp resolution still works on
#: a frozen row) but have no conditions left to assess.
AGRONOMY_COVERAGE_OK = {
    "band-barnes-lshadow":
        "🎸 Barnesy — RETIRED 17-Aug (pm), zero open positions. A retired book "
        "has no growing conditions to scan.",
    "book-schwager-lshadow":
        "🧙 The Wizard — RETIRED 17-Aug (po), undecidable-by-tail. Its 4 open "
        "paper positions are frozen, not managed.",
    "market-context":
        "NOT A BOOK — a market-data publisher. It holds no position, has no "
        "entry rule and no lever surface, so every one of this organ's six "
        "checks is undefined for it (the ROSTER_NON_BOOKS shape (kx)).",
    "book-bezos-lshadow":
        "thin wrapper over lighter_book_douglas_bot with a smaller starting "
        "equity; its BookSpec is identical to douglas and would duplicate it.",
}


def test_every_registered_book_is_visible_to_agronomy():
    """The class: a book the fleet runs must be one this organ can assess, or a
    declared exemption. Silence is not an option."""
    registered = set(fleet_books.ROW_ENTRY)
    specced = set(agronomy.BOOKS)
    missing = sorted(registered - specced - set(AGRONOMY_COVERAGE_OK))
    assert not missing, (
        f"{missing} are in fleet_books.ROW_ENTRY but have no fleet_agronomy "
        "BookSpec, so the organ that asks whether a book has room to grow "
        "cannot answer for them. Add a spec, or declare the omission WITH A "
        "REASON in AGRONOMY_COVERAGE_OK — a silent omission is how a "
        "REAL-MONEY row went unscanned while a retired one was still specced."
    )


def test_the_declared_exemptions_are_real_rows_with_real_reasons():
    """An exemption for a row that no longer exists is stale doctrine, and a
    reason that merely restates the omission is not a reason."""
    registered = set(fleet_books.ROW_ENTRY)
    for row, why in AGRONOMY_COVERAGE_OK.items():
        assert row in registered, (
            f"{row} is declared exempt but is not in ROW_ENTRY — drop the "
            "declaration rather than carrying a rule about nothing")
        assert len(why) > 60 and row.split("-")[0] not in why[:20], (
            f"{row}: the reason must say WHY the omission is correct")


def test_every_live_real_money_row_is_specced_and_marked_live():
    """The sharpest half. A real-money row must be present AND carry live=True
    — a live book specced as shadow is graded by the wrong standard."""
    live_rows = {"perps-funding-lighter-lighter": "💸 the Funding Farmer",
                 "freqtrade-avo-maria-lighter": "🙏 Avo Maria"}
    for row, who in live_rows.items():
        spec = agronomy.BOOKS.get(row)
        assert spec is not None, f"{who} ({row}) — REAL MONEY, and unscanned"
        assert spec.live is True, f"{who} ({row}) is specced but not live=True"
