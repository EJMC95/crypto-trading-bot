#!/usr/bin/env python3
"""scripts/fleet_books.py — THE ONE DECLARATION OF WHICH ROW IS WHICH BOT.

    python3 scripts/fleet_books.py --selftest

WHY THIS FILE EXISTS (2026-08-14 (mn)). The fleet's live roster and its
row->entry-file map were written down in TWELVE places, and `evidence_review`
and `audit_code_currency` carried the SAME `ROW_ENTRY` map maintained twice —
a second copy of a rule is a second rule ((hj)). The cost is not hypothetical:
🙏 Avo Maria's 13-Aug slot swap ((ma)) had to edit ~10 sites in one commit, and
STILL missed CLAUDE.md's own audit-scope rule (caught same day) and both
memories (caught 14-Aug, 22 days stale). The same line had already rotted once
before, on the 17-Jul Tide Rider -> Ticket Taker swap.

THE DISTINCTION THAT MAKES THIS TRACTABLE — two different kinds of fact were
tangled together, and only one of them is derivable:

  * WHICH ROWS ARE LIVE RIGHT NOW is a property of the PAYLOAD
    (`extra.venue == 'lighter_live'`). It must never be written down. Derive it
    — `market_context` deleted its hardcoded roster for exactly this reason and
    is the worked example; `fleet_watchdog_svc` never had one.
  * ROW -> ENTRY FILE / DEPLOY MARKER is a property of the REPO. No payload
    contains it, so it MUST be declared — but ONCE, here, not twelve times.

So this module owns the declarations, and `audit_live_roster.py` is what makes
the arrangement self-correcting: it fails the build when the declared live set
and the DERIVED one disagree, which is what turns the next slot swap into a red
build instead of a doc that rots for three weeks.

WHERE IT LIVES, deliberately. Under `scripts/`, and imported BY other scripts —
the same direction as `golive_readiness` <- `audit_ledger_integrity`. Two
reasons it is not a shipped module: nothing in a container needs it today, and
`bot_pnl_store.py` (the obvious shipped home) is IN the build-stamp file set,
so adding a registry there would re-stamp every image and read the whole fleet
as behind — the (fd) trap. If a shipped organ ever needs this (the respiration
/ impl-shortfall rosters), moving it is a deliberate act with that stamp shift
understood, NOT a quiet import.
"""
from __future__ import annotations

import sys

#: dashboard row -> the ENTRY module whose bytes its image stamps. Explicit
#: rather than inferred: a wrong guess here reports a healthy bot as stale,
#: which is the direction that erodes trust in the guard (I8 — name the object
#: the operator can act on, and be right about it).
ROW_ENTRY = {
    # [2026-08-05] 🎸 Barnesy — mapped the day the row was born, per the (jb)
    # unmapped-row gate (a stamped row this file has never heard of fails the
    # audit rather than being skipped silently).
    "band-barnes-lshadow": "lighter_band_barnes_bot.py",
    # [2026-08-13 (ls)] 🛢️ Garrett — the (lp)/(lr) birth missed this map, and
    # the row began publishing WITH a build stamp on 13-Aug, so the next
    # weekly currency run would have FAILED on an unmapped row. Its entry
    # module is the Farmer's file (FUNDING_VARIANT instance).
    "band-garrett-lshadow": "lighter_funding_bot.py",
    # [2026-08-13 (ls)] 🏦 Rich Dad — mapped the day the row was born, per
    # the same (jb) gate, PRE-provision so its FIRST stamped publish was
    # already covered. Service ALIVE 13-Aug (ls), stamp-verified ((mn)).
    "book-kiyosaki-lshadow": "lighter_book_kiyosaki_bot.py",
    # [2026-08-13 (mb)-(me)] the BOOKS cohort's second wave — mapped the day
    # each row was born, per the (jb) gate, PRE-provision so the FIRST
    # stamped publish was already covered. All four services ALIVE 14-Aug
    # (mk), stamp-verified ((mn)).
    "book-douglas-lshadow": "lighter_book_douglas_bot.py",
    "book-grimes-lshadow": "lighter_book_grimes_bot.py",
    "book-schwager-lshadow": "lighter_book_schwager_bot.py",
    "book-hull-lshadow": "lighter_book_hull_bot.py",
    "book-bezos-lshadow": "lighter_book_bezos_bot.py",
    # [2026-08-18] 🪁 band-kelly — the MIRROR book, mapped the day the row
    # was born, per the (jb) gate, PRE-provision so the FIRST stamped
    # publish is already covered.
    "band-kelly-lshadow": "lighter_band_kelly_bot.py",
    # [2026-08-19 (ri)] 🧭 nav-cook — the NAVIGATOR (the (re) band book),
    # mapped at birth-completion so code-currency can resolve its stamp.
    "nav-cook-lshadow": "lighter_nav_cook_bot.py",
    "crypto-breakout-4h-lshadow": "lighter_family_bot.py",
    "crypto-intraday-15m-lshadow": "lighter_family_bot.py",
    "crypto-swing-daily-lshadow": "lighter_family_bot.py",
    "crypto-trend-daily-lshadow": "lighter_trend_bot.py",
    "freqtrade-avo-maria-lshadow": "lighter_family_bot.py",
    "freqtrade-dad-lshadow": "lighter_family_bot.py",
    "freqtrade-georgia-lshadow": "lighter_family_bot.py",
    "freqtrade-mum-lshadow": "lighter_family_bot.py",
    "equities-regime-lshadow": "lighter_index_bot.py",
    "lighter-dislocation-lshadow": "lighter_dislocation_bot.py",
    "lighter-perp-sniper-lshadow": "lighter_perp_sniper.py",
    # [2026-08-04 (jb)] not a trading bot — the instrument collector — but its
    # row is stamped (measured: build a6219e09bd45 / n=14, svc=market-context)
    # and its image auto-deploys, so currency applies to it exactly as to a
    # bot. It was silently skipped from this guard's first run until the
    # unmapped-row gate below made that impossible.
    "market-context": "market_context.py",
    # [2026-08-13 (ma)] 🙏 Avo Maria took the live slot; the Taker's live row
    # retired. Its entry stays mapped for the transition window — an old
    # container's last stamped publishes must resolve, not read UNMAPPED.
    "freqtrade-avo-maria-lighter": "lighter_avo_live_bot.py",
    "lighter-ticket-taker-lighter": "lighter_ticket_taker.py",
    "lighter-ticket-taker-lshadow": "lighter_ticket_taker.py",
    "perps-funding-carry-lshadow": "funding_carry_bot.py",
    # [2026-08-22 (ta)/(tb)] 💸 the Farmer's live row is RETIRED, and its entry
    # stays mapped for the same reason the Taker's did through (ma): an old
    # container's last stamped publishes must resolve rather than read
    # UNMAPPED. 🔮 georgia now runs on that service.
    "perps-funding-lighter-lighter": "lighter_funding_bot.py",
    "freqtrade-georgia-lighter": "lighter_avo_live_bot.py",
    # [2026-08-25] 👩 mum's live row, mapped PRE-provision per the (jb) gate —
    # the day her service exists and stamps its first publish, currency must
    # resolve it rather than fail on an unmapped row. NOT in DECLARED_LIVE:
    # that set follows the FEED (audit_live_roster), and moves only when the
    # row actually publishes venue=lighter_live. Runbook: MUM_GOLIVE_RUNBOOK.md.
    "freqtrade-mum-lighter": "lighter_avo_live_bot.py",
    "perps-funding-lighter-lshadow": "lighter_funding_bot.py",
    "perps-funding-spread-lshadow": "lighter_funding_spread_bot.py",
    "pm-abbott-lshadow": "parliament_main.py",
    "pm-albanese-lshadow": "parliament_main.py",
    "pm-gillard-lshadow": "parliament_main.py",
    "pm-morrison-lshadow": "parliament_main.py",
    "pm-rudd-lshadow": "parliament_main.py",
    "pm-turnbull-lshadow": "parliament_main.py",
}

#: rows whose service only deploys behind a commit-subject marker, and the
#: marker that does it. Being behind is EXPECTED here unless a marked commit
#: sits in the gap — the distinction the 3-Aug review could not make, which
#: cost it four false ACTION items.
MARKER_GATED = {
    "perps-funding-lighter-lighter": ("[deploy-live-farmer]", "[deploy-live]"),
    # [(tb)] 🔮 georgia's live row — the service kept its gate through the swap
    # but gained its OWN marker, because she and 🙏 Avo share one image and a
    # single marker would restart both books on every fix to either.
    "freqtrade-georgia-lighter": ("[deploy-live-georgia]", "[deploy-live]"),
    "lighter-ticket-taker-lighter": ("[deploy-live-taker]", "[deploy-live]"),
    # [2026-08-13 (ma)] the slot's new occupant deploys behind the SAME
    # marker (the service kept its gate through the swap).
    "freqtrade-avo-maria-lighter": ("[deploy-live-taker]", "[deploy-live]"),
    # [2026-08-25 (te)] 👩 mum's live row — her OWN marker, third book on the
    # shared image; service `mum-live`, fresh sub-account (Eamon's launch
    # order, MUM_GOLIVE_RUNBOOK.md).
    "freqtrade-mum-lighter": ("[deploy-live-mum]", "[deploy-live]"),
    # [2026-08-03] `funding-farmer-shadow` holds ZERO real money and yet is
    # marker-gated, which looks wrong and is not. `(hi)` joined the two arms'
    # deploy CLOCK on purpose: the shadow is the judge's CONTROL arm, and the
    # property that matters is matched-in-BOTH-directions — "auto-deploying
    # the shadow on every unmarked push would simply drift the arms the other
    # way", and the judge's arm-drift gate then refuses every promotion
    # ("this window measures a code delta, not edge").
    #
    # This guard's FIRST live run reported it BEHIND-OWN by 6 commits, which
    # was a gap in this model rather than a fleet defect — recorded here
    # because the finding was checked against the workflow before being
    # believed, and the two arms were in fact byte-identical (both
    # 16c4b139231d) at the moment it fired. A guard that cries wolf on a
    # deliberate design is how a real finding later gets ignored ((hh)).
    "perps-funding-lighter-lshadow": ("[deploy-live-farmer]", "[deploy-live]"),
}

#: [2026-08-04 (jb)] stamped bot_pnl rows DELIBERATELY outside this audit's
#: scope, {row: reason}. fetch_bot_pnl() returns EVERY row in the table, and
#: the old code kept only `b in ROW_ENTRY` — so a stamped row this file had
#: never heard of was skipped silently (market-context, from the guard's first
#: run). An unmapped stamped row now FAILS the audit unless declared here.
#: Empty today ON PURPOSE: every stamped publisher currently has an entry-file
#: mapping, market-context included — a declaration is for a row whose stamp
#: genuinely cannot be resolved to one entry module, not a snooze button.
NON_BOT_ROWS = {}
#: [2026-08-14 (mo)] THE LAST-KNOWN LIVE SET — a TRIPWIRE, never a source of
#: truth. Import-time constants cannot call the network, so a consumer that
#: needs the roster at module scope (evidence_review.LIVE_ROWS) has to declare
#: one. That is exactly the thing that rots, so it is declared HERE, once, and
#: `audit_live_roster.py` fails the build the moment the live feed disagrees
#: with it. Reading order for any consumer that CAN reach the feed:
#: `live_rows_from_feed(doc)` first, this only as the fallback.
DECLARED_LIVE = (
    "freqtrade-avo-maria-lighter",     # 🙏 Avo Maria — (ma) slot swap, 13-Aug
    # [2026-08-22 (tb)] 🔮 georgia — the (ta) slot swap. She runs on
    # `trail-blazer-live`, the service 💸 the Farmer gave up: it was converted
    # in place rather than replaced, so no API key was ever read or moved.
    # Service names in this fleet have never matched their books.
    "freqtrade-georgia-lighter",
    # [2026-08-25 (te)] 👩 mum — the FIRST live book born on a FRESH
    # sub-account rather than a converted slot (Eamon created account
    # 281474976496180 and its keys himself; the provisioner carried them
    # straight into service `mum-live`). Third variant on the shared image.
    "freqtrade-mum-lighter",
)


def live_rows_from_feed(doc):
    """-> sorted [row] the FEED says are live, or None when it cannot say.

    The derivation `market_context` uses, applied to a /pnl.json document:
    a row is live iff its own payload stamps `venue == 'lighter_live'`. This
    survives a slot swap with no edit anywhere, which is the entire point.

    FAIL-CLOSED, and that direction is load-bearing: a dark, empty or
    unparseable feed returns **None** ("I cannot say"), never `[]` ("nothing is
    live"). A network blip must not read as a clean roster — the (kw) rule that
    swept-DARK and swept-CLEAN must never be byte-identical.
    """
    if not isinstance(doc, dict):
        return None
    bots = doc.get("bots")
    if not isinstance(bots, list) or not bots:
        return None                      # an empty feed says nothing
    out, saw_venue = [], False
    for b in bots:
        if not isinstance(b, dict):
            continue
        venue = (b.get("extra") or {}).get("venue") if isinstance(
            b.get("extra"), dict) else None
        if venue is not None:
            saw_venue = True
        if venue == "lighter_live" and b.get("bot"):
            out.append(str(b["bot"]))
    if not saw_venue:
        return None      # no row carried the field at all -> cannot say
    return sorted(out)


def _selftest():
    print("Running fleet_books self-test...\n")

    # -- the registry's own invariants ------------------------------------
    assert set(DECLARED_LIVE) <= set(ROW_ENTRY), \
        "every declared-live row must map to an entry file"
    assert not (set(NON_BOT_ROWS) & set(ROW_ENTRY)), \
        "a row cannot be both mapped and declared a non-bot"
    for row in MARKER_GATED:
        assert row in ROW_ENTRY, f"{row} is marker-gated but unmapped"
    print("  1 registry invariants: live rows mapped, no double-declaration")

    # -- derivation: the happy path ---------------------------------------
    doc = {"bots": [
        {"bot": "a-lighter", "extra": {"venue": "lighter_live"}},
        {"bot": "b-lshadow", "extra": {"venue": "lighter_shadow"}},
        {"bot": "c-lighter", "extra": {"venue": "lighter_live"}}]}
    assert live_rows_from_feed(doc) == ["a-lighter", "c-lighter"]
    print("  2 derives the live set from venue stamps, ignores shadow")

    # -- FAIL-CLOSED: every unusable feed says None, never [] --------------
    # Each of these, if it returned [], would read as "no bot is live" and let
    # a roster-disagreement guard pass vacuously — the exact (kw) shape.
    for bad, why in ((None, "not a dict"), ({}, "no bots key"),
                     ({"bots": []}, "empty bots"),
                     ({"bots": "nope"}, "bots not a list"),
                     ({"bots": [{"bot": "x"}]}, "no venue field anywhere"),
                     ({"bots": [{"bot": "x", "extra": None}]}, "extra is None")):
        got = live_rows_from_feed(bad)
        assert got is None, f"{why}: expected None (cannot say), got {got!r}"
    print("  3 fail-CLOSED: a dark/empty/fieldless feed says None, never []")

    # a feed that CAN say, and says nothing is live, is a real answer ([])
    assert live_rows_from_feed(
        {"bots": [{"bot": "x", "extra": {"venue": "lighter_shadow"}}]}) == []
    print("  4 ...but a readable feed with zero live rows IS an answer ([])")

    print("\nfleet_books self-tests passed.")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        print(f"{len(ROW_ENTRY)} rows mapped; declared live: "
              f"{', '.join(DECLARED_LIVE)}")
