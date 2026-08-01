"""The go-live gate counts a book's CURRENT self, not its whole ledger.

[2026-07-30 (hc)] `scripts/golive_readiness.py` graded every book on its entire
retained ledger, so a change that made the earlier record WRONG kept counting
toward the 30-day bar. Measured on the book nearest to real money — 🌾
`perps-funding-carry-lshadow`, the fleet's frontrunner at five of six bars:

    opened BEFORE 2026-07-17   n=25   +$62.03
    opened SINCE  2026-07-17   n=57   -$0.91

101% of its realised P&L (+$62.03 of +$61.12) was opened before 17-Jul, the
date its `lighter_shadow` arm's accrual basis was fixed from per-hour to the
venue's own per-8h settlement. For a funding book the accrual IS the P&L. The
pooled grade read mean +0.248%, t=+2.60, both halves positive; the in-era grade
reads mean -0.005%, t=-0.08 and TWO of six bars.

WHAT THESE TESTS PIN, in order of what would hurt most if it broke:

 1. The era RESTRICTS. A book whose profit predates its era must grade worse
    in-era than all-time, or the block is decoration.
 2. It is keyed on the OPEN. A trade's policy is fixed when it is taken.
 3. It FAILS CLOSED. An unreadable open stamp is excluded when an era is
    declared — counting a trade whose era cannot be determined is exactly the
    credit being withdrawn.
 4. Absence of an era changes NOTHING. Every other book still grades all-time.
 5. It cannot be WEAPONISED. Ordinary tuning must not reset an era, or the
    growth rail — which moves levers continuously by design — would keep every
    book's clock at zero and no book could ever be promoted.
 6. An era'd book cannot VANISH from the report. Its thinner sample must show
    dark bars, not drop below the min-closes filter and disappear.
"""
import pathlib
import sys
import datetime as _dt

import pytest

pytestmark = pytest.mark.autonomy

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "scripts"))

import golive_readiness as g          # noqa: E402

#: The synthetic era used by payload/card fixtures below. Deliberately a date
#: NO era table owns, so a real era move cannot break a test about rendering.
FIXTURE_ERA_ISO = "2026-06-01"

CARRY = "perps-funding-carry-lshadow"


def _p(x):
    """Stand-in for experiment_judge.parse_ts — epoch seconds from an ISO str."""
    from datetime import datetime, timezone
    d = datetime.fromisoformat(str(x))
    return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).timestamp()


def _rows(pcts, start="2026-07-01", step_h=6.0):
    """[(profit_ratio, profit_abs, close_dt)] plus matching open stamps."""
    from datetime import datetime, timedelta, timezone
    t0 = datetime.fromisoformat(start).replace(tzinfo=timezone.utc)
    out = []
    for i, p in enumerate(pcts):
        ts = t0 + timedelta(hours=step_h * i)
        out.append((p, p * 300.0, ts))
    return out


# --------------------------------------------------------------------------
# 1. The era RESTRICTS — the property that makes this more than a label.
# --------------------------------------------------------------------------

def test_the_era_grades_a_front_loaded_book_strictly_worse():
    """The shape of the real finding, in synthetic form: all the profit in the
    early segment, flat since. All-time passes on mean/t; in-era must not."""
    early = _rows([0.02] * 25, start="2026-07-05")
    late = _rows([0.0002, -0.0002] * 20, start="2026-07-20")
    s_all, s_era = g.stats(early + late), g.stats(late)
    assert s_all["mean_pct"] > 0 and s_all["t"] >= g.GOLIVE_MIN_T, s_all
    assert g.bar_map(s_era)["t"] is False, s_era
    assert sum(g.bar_map(s_era).values()) < sum(g.bar_map(s_all).values()), (
        "the era-scoped sample must grade no better than all-time on a book "
        "whose edge predates it — otherwise this block restricts nothing")


def test_the_carry_declaration_carries_its_measurement():
    """The numbers must travel WITH the exemption. A reason that says 'the
    accrual basis changed' without the split lets the next reader re-open the
    question from prose instead of from the measurement."""
    iso, why = g.POLICY_ERA["perps-funding-carry"]
    # [(ii)] MOVED 17-Jul -> 31-Jul: a 12-day TWO-WRITER window (7 same-pair
    # overlaps, deepest 9.14h on HYPE, peak 10 concurrent against a cap of 8)
    # makes the earlier sample two books' trades, not this book's — a stronger
    # invalidation than a wrong accrual unit. An era is the LATEST of every
    # invalidating change, so the declaration must still carry the EARLIER
    # reason: moving a date forward preserves it rather than discarding it.
    # The DATE is the table's business and is deliberately NOT pinned here —
    # pinning it made a correct table move read as a failure ((ii)). What must
    # hold is that the declaration carries the MEASUREMENT it rests on.
    assert iso and _dt.datetime.fromisoformat(iso), iso
    assert "9.14" in why and "claim_writer" in why, (
        "the declaration must quote the two-writer measurement it now rests on")
    assert "accrual" in why.lower(), (
        "an era is the LATEST of every invalidating change — the superseded "
        "accrual-basis reason must survive in the declaration, not vanish")


# --------------------------------------------------------------------------
# 2. Keyed on the OPEN, not the close.
# --------------------------------------------------------------------------

def test_a_trade_that_straddles_the_boundary_is_excluded():
    """Opened under the old basis, closed under the new one. It accrued in BOTH,
    so it describes neither era — and its close date would smuggle it in."""
    # Era-relative, so a declared-era move does not break a test about the
    # BOUNDARY RULE. (This pinned 2026-07-17 literals until (ii).)
    era_iso = g.POLICY_ERA[g.era_base(CARRY)][0]
    era_d = _dt.datetime.fromisoformat(era_iso).replace(tzinfo=_dt.timezone.utc)
    ep, _, _ = g.era_epoch_for(CARRY)
    before = (era_d - _dt.timedelta(hours=12)).isoformat()
    assert g.in_era(before, ep, _p) is False, (
        "a pre-era OPEN must be excluded however late it closed")
    assert g.in_era(era_d.isoformat(), ep, _p) is True, "the boundary is inclusive"


def test_the_era_is_read_off_the_OPEN_stamp_not_the_close():
    """The wiring, not the arithmetic. `in_era` could be perfect and the caller
    could still hand it the CLOSE stamp — the repo's 'the selftest proves the
    arithmetic and not the CALL SITE' trap.

    [2026-07-31 (hq)] REWRITTEN FROM A SUBSTRING TO THE INVARIANT. This asserted
    the literal `in_era(r.get("open_ts")` appeared in the grader. That pinned one
    SPELLING of the wiring, not the wiring: when `era_rows` became the single
    owner of the filter (so the daily review could stop grading a book's whole
    retained ledger) the call moved one function and the literal vanished, while
    the property it protects was untouched. A substring scan is not a structural
    claim — CLAUDE.md doctrine, and the reason it is worth restating here is that
    this test's failure was briefly read as evidence the refactor was broken.

    The functional form below cannot be satisfied by any spelling: it feeds a
    trade OPENED before the era and CLOSED well inside it. Keyed on the open it
    is excluded; keyed on the close it is kept. A straddler belongs to neither
    era and excluding it is the conservative reading."""
    from datetime import datetime, timedelta, timezone
    ep, iso, _ = g.era_epoch_for(CARRY)
    assert ep, "this test needs a book with a declared era"
    boundary = datetime.fromisoformat(iso).replace(tzinfo=timezone.utc)

    straddler = (0.05, 50.0,
                 boundary + timedelta(days=10),        # closed INSIDE the era
                 (boundary - timedelta(days=3)).isoformat())   # opened BEFORE
    clean = (0.01, 10.0,
             boundary + timedelta(days=11),
             (boundary + timedelta(days=1)).isoformat())

    scoped, all_time, got_iso = g.era_rows(CARRY, [straddler, clean])
    assert got_iso == iso
    assert len(all_time) == 2, "the all-time sample keeps everything"
    assert len(scoped) == 1 and scoped[0][1] == 10.0, (
        "the era must be keyed on the trade's OPEN stamp — a position opened "
        "before the boundary accrued under the old policy for part of its life "
        "and belongs to neither era")


def test_the_grading_loop_hands_era_rows_the_open_stamp():
    """The other half of the wiring: `era_rows` reads element [3] of each row,
    so the grading loop must actually PUT the open stamp there. Checked on the
    source because the loop's DB read is not unit-testable offline."""
    src = (_ROOT / "scripts/golive_readiness.py").read_text()
    assert 'r.get("open_ts")))' in src or 'r.get("open_ts")' in src, (
        "the grading loop must carry the trade's OPEN stamp into era_rows")
    assert "era_rows(bot, quads" in src, (
        "the grading loop must route through era_rows, not filter inline")


# --------------------------------------------------------------------------
# 3. Fail-closed.
# --------------------------------------------------------------------------

@pytest.mark.parametrize("bad", [None, "", "not-a-date", "2026-13-45"])
def test_an_unreadable_open_stamp_is_excluded_when_an_era_is_declared(bad):
    ep, _, _ = g.era_epoch_for(CARRY)
    assert g.in_era(bad, ep, _p) is False, bad


@pytest.mark.parametrize("bad", [None, "", "not-a-date"])
def test_the_same_stamp_is_INCLUDED_when_no_era_is_declared(bad):
    """No era means no claim about which trades count. Excluding rows from an
    undeclared book would silently shrink every other book's sample."""
    assert g.in_era(bad, None, _p) is True, bad


# --------------------------------------------------------------------------
# 4. Additive — no other book moves.
# --------------------------------------------------------------------------

@pytest.mark.parametrize("bot", [
    # publishers that do NOT accrue funding — a price book's P&L cannot carry an
    # accrual defect, so declaring an era for it would discard real evidence for
    # nothing. Verified against the `[2026-07-17 BASIS FIX]` set.
    "lighter-dislocation-lshadow",
    "lighter-perp-sniper-lshadow",
    "pm-gillard-lshadow",
    "pm-abbott-lshadow",
])
def test_an_undeclared_book_still_grades_all_time(bot):
    assert g.era_epoch_for(bot) == (None, None, None), (
        f"{bot} gained a policy era — that changes its published verdict and "
        "needs its own declaration and measurement")


# --------------------------------------------------------------------------
# 4b. THE REAL-MONEY PAIR. [(hg)]
# --------------------------------------------------------------------------

FARMER_LIVE = "perps-funding-lighter-lighter"
FARMER_SHADOW = "perps-funding-lighter-lshadow"


@pytest.mark.parametrize("bot", [FARMER_LIVE, FARMER_SHADOW])
def test_the_funding_farmer_pair_is_scoped_to_the_basis_fix(bot):
    """💸 The same per-hour/per-8h accrual fix, on a pair that includes a
    REAL-MONEY book. ONE bare key covers both rows — that is the whole reason
    `era_epoch_for` strips suffixes, and getting it wrong here would scope the
    shadow twin while leaving the live row pooled."""
    ep, iso, why = g.era_epoch_for(bot)
    # Derived: under test is the SUFFIX STRIP, not the date ((ii)).
    assert ep is not None and iso == g.POLICY_ERA[g.era_base(bot)][0], (bot, ep, iso)
    assert "REAL-MONEY" in why or "real-money" in why, why


def test_the_BRAINS_strip_handles_the_farmers_self_suffixed_name_too():
    """`bot_learn.era_epoch_for` had its own copy of the double-strip, and the
    grader's tests could not see it — a mutation restoring the old strip in
    bot_learn.py left this file GREEN. That gap matters more than the grader's:
    the brain grades the LIVE Farmer row and has had jurisdiction over its tag
    since (bb), so a half-resolving era means the brain keeps forming hypotheses
    from 8x-inflated win rates on a real-money book while the gate does not."""
    import bot_learn
    base = bot_learn.era_epoch_for("perps-funding-lighter")
    assert base is not None, (
        "the bare key does not resolve to itself — `-lighter` is part of this "
        "book's NAME, so a two-strip mangles it to 'perps-funding'")
    for row in ("perps-funding-lighter-lighter", "perps-funding-lighter-lshadow"):
        assert bot_learn.era_epoch_for(row) == base, (
            f"{row} resolves to a different era than the bare key — the live row "
            f"and its shadow twin would be graded on different samples")
    # and no existing entry moved: every other row carries a single suffix
    assert bot_learn.era_epoch_for("freqtrade-mum-lshadow") is not None
    assert bot_learn.era_epoch_for("pm-gillard-lshadow") is None


def test_the_farmer_declaration_records_that_no_post_fix_window_passes_t():
    """The measurement that made this urgent rather than tidy. The shadow twin
    was reported as the fleet's go-live frontrunner at 5/6 / t=+2.09; in-era it
    is 3/6 / t=+0.74 with h1 NEGATIVE, and NO post-fix boundary clears t>=2.0.
    All-time is the single window in which the book looks ready — which is the
    signature of an artifact, not of an edge."""
    _ep, _iso, why = g.era_epoch_for(FARMER_SHADOW)
    assert "5/6" in why and "3/6" in why, why
    assert "no post-fix boundary passes the t" in why.lower(), why


def test_the_promotion_judge_is_era_safe_BY_CONSTRUCTION():
    """Checked, not assumed — this is the pipeline that is the ONLY writer of
    `live.funding.*` on a real-money book, so "probably fine" is not an answer.
    Every arm comparison goes through `arm_trades(rows, bot, start_ts, end_ts)`
    and the windows begin at the candidate's own `started_ts`, all of which
    postdate 17-Jul. If that windowing is ever removed, the judge starts pooling
    pre-fix rows into a paired real-money comparison and needs its own era."""
    src = (_ROOT / "experiment_judge.py").read_text()
    assert "arm_trades(rows, shadow_bot, start_ts, end_ts" in src
    assert "arm_trades(rows, live_bot, start_ts, end_ts" in src, (
        "the judge no longer windows the LIVE arm from the candidate's start — "
        "it would now pool pre-basis-fix rows into a real-money promotion bar")


def test_the_ticket_taker_IS_an_accruing_book_and_is_scoped_too():
    """The other real-money book, and I had this WRONG. I first wrote this test
    asserting the taker needs no era because "it is a price book" — and the test
    failed, because it DOES accrue funding: its divergence lens exists to collect
    the credit, and it carried the same 8x defect *modelled inline*, so the
    17-Jul grep for the fixed call site missed it ("the THIRD accruing book to
    carry this bug"). Its own note says the accrual "reaches the per-trade ledger
    and the win/loss call" and "flattered the one number that could earn this bot
    a go-live". The assumption was the defect; the test caught it."""
    src = (_ROOT / "lighter_ticket_taker.py").read_text()
    assert "funding_basis.to_hourly" in src, (
        "the taker no longer accrues funding — re-read whether its era still "
        "describes anything")
    for row in ("lighter-ticket-taker-lighter", "lighter-ticket-taker-lshadow"):
        ep, iso, _why = g.era_epoch_for(row)
        assert ep is not None and iso == g.POLICY_ERA[g.era_base(row)][0], (row, ep, iso)


@pytest.mark.parametrize("bot,publisher", [
    ("perps-funding-carry", "funding_carry_bot.py"),
    ("perps-funding-lighter", "lighter_funding_bot.py"),
    ("lighter-ticket-taker", "lighter_ticket_taker.py"),
    ("perps-funding-spread", "lighter_funding_spread_bot.py"),
    ("freqtrade-georgia", "lighter_family_bot.py"),
    ("freqtrade-dad", "lighter_family_bot.py"),
    ("crypto-intraday-15m", "lighter_family_bot.py"),
    ("crypto-breakout-4h", "lighter_family_bot.py"),
])
def test_every_basis_era_names_a_publisher_that_really_accrues(bot, publisher):
    """Membership is RULE-DRIVEN, not a list I curated: the book's publisher must
    carry the 17-Jul basis fix on an accrual line. Without this the table drifts
    into "books whose numbers someone looked at", which is how a uniform rule
    becomes cherry-picking."""
    assert bot in g.POLICY_ERA, f"{bot} lost its era"
    src = (_ROOT / publisher).read_text()
    # The marker text is NOT uniform — `funding_carry_bot` labels its own as
    # "[2026-07-17 THE SIXTH 8x BOT]" rather than "BASIS FIX". Matching on the
    # DATE plus a real rate conversion is the invariant; matching on one house
    # phrase was my test asserting a convention the fleet does not have.
    _era_day = g.POLICY_ERA[g.era_base(bot)][0][:10]
    assert _era_day in src, (
        f"{publisher} carries no {_era_day} dated note — the publisher's own "
        "record of the change must name the date its era is declared from")
    assert ("to_hourly" in src or "_hourly(" in src), (
        f"{publisher} does not convert a funding rate — if it never accrued, "
        f"{bot}'s era describes nothing and should be removed")


def test_the_non_accruing_books_are_excluded_ON_PURPOSE():
    """The other half of the rule, and the more dangerous half to get wrong: an
    era declared "for symmetry" on a price book throws away real evidence in
    exchange for nothing."""
    for publisher, row in (("lighter_dislocation_bot.py", "lighter-dislocation"),
                           ("lighter_perp_sniper.py", "lighter-perp-sniper")):
        src = (_ROOT / publisher).read_text()
        assert "funding_basis.to_hourly" not in src, (
            f"{publisher} now accrues funding — it needs an era declaration and "
            f"this test needs re-reading")
        assert row not in g.POLICY_ERA, f"{row} gained an era but does not accrue"


def test_the_suffix_is_stripped_like_the_brains_table():
    """The table is keyed BARE; the ledger's `bot` carries `-lshadow`/`-lighter`.
    The brain shipped that mismatch for nine days and every book was graded on
    its whole ledger as a result (bot_learn.era_epoch_for, 23-Jul audit). Same
    hazard, same fix, pinned here so it cannot regress in the copy."""
    bare = g.era_epoch_for("perps-funding-carry")
    for suffixed in ("perps-funding-carry-lshadow", "perps-funding-carry-lighter"):
        assert g.era_epoch_for(suffixed) == bare, suffixed


def test_every_declaration_is_parseable_and_reasoned():
    for base, ent in g.POLICY_ERA.items():
        assert isinstance(ent, tuple) and len(ent) == 2, base
        iso, why = ent
        ep, got_iso, got_why = g.era_epoch_for(base)
        assert ep is not None and got_iso == iso, base
        assert len(why) > 80, f"{base}: the era's reason is too thin to review"
        # A key must RESOLVE TO ITSELF. The old form of this test asserted
        # `"-lighter" not in base`, which is wrong for the one book that matters:
        # 💸 Funding Farmer is NAMED `perps-funding-lighter`. The real invariant
        # is that `era_base` maps the key back to the key — that is what makes it
        # reachable from a ledger row — and it is what catches a key typed with a
        # row suffix as well.
        assert g.era_base(base) == base, (
            f"{base} does not resolve to itself — era_base maps it to "
            f"{g.era_base(base)!r}, so this entry can never match a ledger row")
        assert "-lshadow" not in base, f"{base} is keyed with a shadow suffix"


# --------------------------------------------------------------------------
# 5. It cannot be weaponised into never promoting anything.
# --------------------------------------------------------------------------

def test_ordinary_tuning_is_NOT_an_era_reset():
    """Carry's own ENTER_APR 0.40 -> 1.60 (21-Jul, enacted from a sweep) is the
    worked example: a real, deliberate, measured policy change that is still not
    an era reset. Splitting there would restrict the book FURTHER (n=31,
    -$0.76), so this is not laziness — the growth rail moves levers every day by
    design, and a guard that reset the clock on each move would make the 30-day
    bar unreachable for every book forever."""
    iso, _ = g.POLICY_ERA["perps-funding-carry"]
    assert iso != "2026-07-21", (
        "the era was moved to the lever change — re-read the RESET/DO-NOT rule "
        "in POLICY_ERA before doing this; it makes go-live unreachable")
    src = (_ROOT / "scripts/golive_readiness.py").read_text()
    assert "DO NOT     ordinary tuning" in src, (
        "the rule limiting what resets an era must stay written down next to "
        "the table it governs")


def test_the_gate_still_promotes_nothing():
    """An era is a REPORTING scope. It must not have acquired an actuator.

    By AST, not by substring: the docstring says the file 'flips no dry_run', so
    a text scan for the token fails on the very sentence that promises the
    property. Same lesson as (hb) — a structural claim needs a structural check.
    """
    import ast
    src = (_ROOT / "scripts/golive_readiness.py").read_text()
    forbidden = {"set_lever", "get_lever", "place_order", "create_order",
                 "save_lever", "publish"}
    called = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Call):
            fn = node.func
            nm = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
            if nm in forbidden:
                called.add(nm)
    assert not called, (
        f"golive_readiness now CALLS {sorted(called)} — this file grades and "
        "publishes state; go-live remains an explicit operator act")


# --------------------------------------------------------------------------
# 6. An era'd book must not disappear from the report.
# --------------------------------------------------------------------------

def test_a_thin_era_is_publishable_not_a_crash():
    thin = g.stats(_rows([0.01]))
    bp = g.book_payload(thin)
    assert bp["n"] == 1 and bp["days"] is None
    assert set(bp["bars"]) == set(g.BAR_NAMES) and bp["bars_passed"] == 0


def test_the_min_closes_filter_is_applied_to_the_ALL_TIME_count(capsys,
                                                               monkeypatch):
    """The demotion must be visible. If `--min-closes` were applied to the
    era-scoped count, a book whose era is thin would silently vanish from the
    report — and vanishing reads as 'not a candidate', which is indistinguishable
    from 'never was one'. Drives the REAL main() so this is the wiring, not a
    restatement of the comment."""
    import bot_pnl_store as store
    # [(ii)] Dates are ERA-RELATIVE, not literals. This test pinned 2026-07-17
    # in three places, so moving carry's declared era (17-Jul -> 31-Jul, when
    # the 12-day two-writer window was found) broke it for no reason connected
    # to what it checks. It exists to prove the MECHANISM — min-closes applied
    # to the all-time count, and the era keyed on the OPEN — so it now reads
    # the declared era and builds its fixture around it.
    era_iso = g.POLICY_ERA[g.era_base(CARRY)][0]
    era_d = _dt.datetime.fromisoformat(era_iso).replace(tzinfo=_dt.timezone.utc)

    def _at(days, hour=0):
        return (era_d + _dt.timedelta(days=days, hours=hour)).isoformat()

    rows = []
    for i in range(40):                       # 40 closes, all BEFORE the era
        rows.append({"bot": CARRY, "profit_abs": 3.0, "profit_ratio": 0.01,
                     "open_ts": _at(-10 - (i % 5)),
                     "close_ts": _at(-10 - (i % 5), 6)})
    for i in range(3):                        # 3 closes inside it
        rows.append({"bot": CARRY, "profit_abs": -0.1, "profit_ratio": -0.0003,
                     "open_ts": _at(1 + i),
                     "close_ts": _at(1 + i, 6)})
    # ...and ONE STRADDLER: opened under the old policy, closed well inside the
    # era. This row is what makes the count below discriminating — key the era
    # on the close stamp and it becomes "4 of 44", which is the bug.
    rows.append({"bot": CARRY, "profit_abs": 9.0, "profit_ratio": 0.03,
                 "open_ts": _at(-2), "close_ts": _at(8)})
    monkeypatch.setattr(store, "fetch_paper_trades", lambda limit=2000: rows)
    monkeypatch.setattr(sys, "argv", ["golive_readiness.py", "--min-closes", "10"])
    g.main()
    out = capsys.readouterr().out
    assert CARRY in out, (
        "an era'd book with a thin era vanished from the report instead of "
        "showing dark bars — a demotion must be readable")
    assert f"era {era_iso}" in out, "the report does not say it scoped the sample"
    assert "3 of 44 closes count" in out, out
    assert "READY: none" in out


# --------------------------------------------------------------------------
# 6b. The brain and the gate must describe the SAME book. [(hd)]
# --------------------------------------------------------------------------

def test_the_brain_scopes_the_carry_book_to_the_same_era():
    """[(hd)] `bot_learn.ERA_START` exists for exactly this — "hypotheses must
    come from trades taken by the CURRENT code" — and had no carry entry, so the
    brain graded the pre-fix and post-fix accrual bases together. It carries an
    ACTUATOR-bearing `regime_gate` diagnosis on this book's `long` bucket, whose
    entire positive evidence is 3 pre-fix decay wins."""
    import bot_learn
    # The VALUE belongs to bot_learn.ERA_START, which owns it; duplicating it
    # here is what breaks on a legitimate move ((ii)). Assert that the brain
    # scopes the book at all, and that it parses — the gate>=brain RELATION has
    # its own test below.
    _brain = bot_learn.ERA_START.get("perps-funding-carry")
    assert _brain and _dt.datetime.fromisoformat(str(_brain)), _brain
    assert bot_learn.era_epoch_for("perps-funding-carry-lshadow") is not None


def test_the_gates_sample_is_never_WIDER_than_the_brains():
    """Two organs, two tables, one book — and they answer different questions,
    so "must be equal" was the wrong invariant. `freqtrade-georgia` proves it:
    the brain scopes from 13-Jul for a STRATEGY change and the gate from 17-Jul
    for an ACCOUNTING one. Both are right about their own question.

    The invariant that IS meaningful and directional: **the gate's era must be at
    least as late as the brain's.** A promotion sample may never be wider than
    the sample the brain is willing to form a hypothesis from — the gate decides
    real money and must be the more conservative of the two.

    STANDING FOLLOW-UP, recorded here rather than lost: four family/spot books
    carry brain eras EARLIER than 17-Jul (georgia 13-Jul, dad 14-Jul, mum 14-Jul,
    crypto-intraday-15m 13-Jul), so the brain still pools pre-basis-fix accrual
    for them. Moving those to 17-Jul is strictly narrower and strictly more
    correct, but it changes hypothesis generation on several shadow books and
    deserves its own measured pass — not a side effect of a real-money commit."""
    import bot_learn
    from datetime import datetime
    for base, (iso, _why) in g.POLICY_ERA.items():
        brain = bot_learn.ERA_START.get(base)
        if brain is None:
            continue
        gate_d = datetime.fromisoformat(iso)
        brain_d = datetime.fromisoformat(brain)
        assert gate_d >= brain_d.replace(tzinfo=None), (
            f"{base}: the go-live gate scopes from {iso}, EARLIER than the "
            f"brain's {brain} — the gate decides real money and must never grade "
            f"a wider sample than the brain will hypothesise from")


def test_no_LIVING_book_is_scoped_by_the_brain_but_not_by_the_gate():
    """[(hh)] The other direction, and the one that bites silently. A book the
    brain scopes and the gate does NOT is a book the gate grades ALL-TIME — the
    looser of the two, on the side that decides real money. It reads as fine
    until the day the book crosses the report's min-closes floor, and nobody
    thinks to add an era then. Retired books are excluded: they are history and
    the liveness filter drops them before any lookup."""
    import bot_learn
    from cleanup_legacy_bots import LEGACY_BOTS
    retired_bases = {g.era_base(b) for b in LEGACY_BOTS}
    # the two entries deliberately frozen pre-accrual-fix are RETIRED strategies
    frozen = {"crypto-trendmomo-4h", "perps-regime-switch"}
    missing = [b for b in bot_learn.ERA_START
               if b not in g.POLICY_ERA and b not in retired_bases
               and b not in frozen]
    assert not missing, (
        f"the brain scopes {missing} and the go-live gate does not — the gate "
        "would grade them all-time, i.e. wider than the brain, on whatever day "
        "they become gradeable")


# --------------------------------------------------------------------------
# 7. The operator has to be able to SEE that the sample was scoped.
# --------------------------------------------------------------------------

def _card(books, monkeypatch):
    import pnl_dashboard as dash
    monkeypatch.setattr(dash, "fetch_states", lambda keys: {
        "golive-readiness": {
            "updated": "2026-07-30T00:00:00+00:00", "ttl_sec": g.TTL_SEC,
            "bar": {"min_days": g.GOLIVE_MIN_DAYS,
                    "min_closes": g.GOLIVE_MIN_CLOSES,
                    "min_t": g.GOLIVE_MIN_T, "max_dd": g.GOLIVE_MAX_DD},
            "bar_names": list(g.BAR_NAMES), "books": books, "ready": []}})
    return dash.golive_card()


def _era_book():
    era = g.stats(_rows([0.0002, -0.0002] * 20, start="2026-07-20"))
    alltime = g.stats(_rows([0.02] * 25, start="2026-07-05")
                      + _rows([0.0002, -0.0002] * 20, start="2026-07-20"))
    b = {**g.book_payload(era), "fails": g.grade(era)[1],
         "ready": False, "legacy_ready": False,
         # A SYNTHETIC era date on purpose: this fixture tests payload SHAPE,
         # so coupling it to a real declared era would break it whenever that
         # era legitimately moves ((ii)). Named once, derived by every assertion.
         "era": {"since": FIXTURE_ERA_ISO, "why": "the accrual basis changed",
                 "closes_in_era": era["n"], "closes_all_time": alltime["n"]},
         "alltime": g.book_payload(alltime)}
    return b


def test_the_card_says_a_book_was_graded_on_part_of_its_ledger(monkeypatch):
    """`n40` beside a book whose row reports 65 closes is unreadable without
    this. The chip is the only thing tying the bars to the sample they came from.
    """
    out = _card({CARRY: _era_book()}, monkeypatch)
    assert f">era {FIXTURE_ERA_ISO[5:]}</span>" in out, out[:400]
    assert "40 of 65 closes" in out, "the chip must quote both counts"


def test_the_card_carries_the_all_time_reading_it_replaced(monkeypatch):
    """Withdrawing credit silently is how a demotion looks like a bug. The
    tooltip has to show what the pooled sample WOULD have said."""
    out = _card({CARRY: _era_book()}, monkeypatch)
    assert "All-time would read" in out, out[:600]


# --------------------------------------------------------------------------
# 8. LEDGER INTEGRITY is a PRECONDITION, not a seventh bar. [(hf)]
# --------------------------------------------------------------------------

def _eps(*spans):
    """(pair, open, close) episodes from (pair, open_h, close_h) triples."""
    from datetime import datetime, timedelta, timezone
    t0 = datetime(2026, 7, 20, tzinfo=timezone.utc)
    return [(p, t0 + timedelta(hours=o), t0 + timedelta(hours=c))
            for p, o, c in spans]


def test_one_process_sequential_holds_are_clean():
    """Close-and-reopen on the same symbol is the NORMAL shape — the bot deletes
    the position and the entry block runs later in the same loop, so open2 ==
    close1. If that fired, every book in the fleet would read as compromised."""
    assert g.same_pair_overlaps(_eps(("BTC", 0, 5), ("BTC", 5, 9))) == []
    assert g.peak_concurrency(_eps(("BTC", 0, 5), ("ETH", 1, 4))) == 2


def test_a_hold_opening_INSIDE_another_on_one_symbol_is_two_writers():
    """The detector. A carry process keys `positions` by coin and enters only
    `if c not in positions`, so this shape is structurally impossible for one
    process — which is what makes it proof rather than a heuristic."""
    hits = g.same_pair_overlaps(_eps(("BTC", 0, 5), ("BTC", 3, 8)))
    assert len(hits) == 1 and abs(hits[0][1] - 2.0) < 1e-9, hits


def test_sub_threshold_jitter_does_not_fire():
    from datetime import datetime, timedelta, timezone
    t0 = datetime(2026, 7, 20, tzinfo=timezone.utc)
    eps = [("BTC", t0, t0 + timedelta(hours=5)),
           ("BTC", t0 + timedelta(hours=5, seconds=-30), t0 + timedelta(hours=9))]
    assert g.same_pair_overlaps(eps) == [], "30s of loop jitter is not a writer"


def test_a_two_writer_book_can_never_be_READY(capsys, monkeypatch):
    """The whole point of wiring it into the grader. A flawless book on all six
    bars must still be refused if its ledger cannot have come from one process —
    `n` is not one book's trades and `t` scales with sqrt(n). Fail-closed."""
    import bot_pnl_store as store
    rows = []
    for i in range(40):        # 40 clean sequential winners over 40 days
        rows.append({"bot": "book-dup", "pair": f"C{i}", "profit_abs": 3.0,
                     "profit_ratio": 0.01,
                     "open_ts": f"2026-06-{1 + i % 28:02d}T00:00:00+00:00",
                     "close_ts": f"2026-07-{1 + i % 28:02d}T00:00:00+00:00"})
    monkeypatch.setattr(store, "fetch_paper_trades", lambda limit=2000: rows)
    monkeypatch.setattr(sys, "argv", ["golive_readiness.py", "--min-closes", "10"])
    g.main()
    clean = capsys.readouterr().out
    assert "book-dup" in clean

    # now add ONE overlapping pair — nothing else changes
    rows.append({"bot": "book-dup", "pair": "C0", "profit_abs": 3.0,
                 "profit_ratio": 0.01,
                 "open_ts": "2026-06-02T00:00:00+00:00",
                 "close_ts": "2026-07-05T00:00:00+00:00"})
    g.main()
    out = capsys.readouterr().out
    assert "TWO WRITERS" in out, out[-1200:]
    assert "READY: none" in out or "book-dup" not in (
        out.split("READY:")[-1]), "a two-writer book must never be READY"


def test_the_card_shouts_when_a_ledger_has_two_writers(monkeypatch):
    b = _era_book()
    b["integrity"] = {"two_writers": True, "same_pair_overlaps": 7,
                      "deepest_overlap_h": 9.14, "deepest_overlap_pair": "HYPE",
                      "peak_concurrent": 10}
    out = _card({CARRY: b}, monkeypatch)
    assert ">2 writers</span>" in out, out[:500]
    assert "HYPE" in out and "stop the duplicate service" in out.lower()


def test_the_card_is_silent_when_the_ledger_is_clean(monkeypatch):
    b = _era_book()
    b["integrity"] = {"two_writers": False, "same_pair_overlaps": 0,
                      "deepest_overlap_h": 0.0, "deepest_overlap_pair": None,
                      "peak_concurrent": 4}
    out = _card({CARRY: b}, monkeypatch)
    assert ">2 writers</span>" not in out


def test_the_audit_and_the_gate_share_ONE_owner():
    """A second copy of the detector would let the audit and the gate disagree
    about the same ledger. The audit imports the grader's primitives; the
    reverse would drag a non-shipped script into the freqtrade image's import
    graph, which is the born-dark class."""
    src = (_ROOT / "scripts/audit_ledger_integrity.py").read_text()
    assert "from golive_readiness import" in src
    assert "\ndef same_pair_overlaps(" not in src, (
        "the audit re-defines the detector — one owner or they will drift")
    assert "\ndef peak_concurrency(" not in src
    import audit_ledger_integrity as a
    assert a.same_pair_overlaps is g.same_pair_overlaps
    assert a.peak_concurrency is g.peak_concurrency


def test_a_book_with_no_era_key_renders_unchanged(monkeypatch):
    """Backwards compatibility in the safe direction: a payload from a publisher
    that predates (hc) has no `era` key at all, and must render exactly as
    before rather than showing an empty chip.

    Checked against the CHIP's own markup, not the bare word "era" — that
    appears in the card's footer ("explicit operator act"), so a substring scan
    fails on the sentence promising the property. Third time this file has hit
    that; the lesson is that a page-wide text scan is not a structural claim."""
    s = g.stats(_rows([0.01] * 40))
    plain = {**g.book_payload(s), "fails": [], "ready": False,
             "legacy_ready": False}
    out = _card({"book-plain": plain}, monkeypatch)
    assert "book-plain" in out
    assert ">era " not in out, "a book with no declared era grew an era chip"
    assert "closes count" not in out and "All-time would read" not in out


# --------------------------------------------------------------------------
# 7. INTEGRITY IS EVALUATED OVER THE GRADED SAMPLE. [(ii)] 01-Aug
#
# `(hf)` scoped the blocking check to the WHOLE ledger — right about detection,
# wrong about blocking. A ledger is append-only, so an all-time check is a
# ONE-WAY LATCH: once true it is true forever however thoroughly the cause is
# fixed. 🌾 carry, the fleet's only book with a measured claim, could never be
# READY again on 7 overlaps all falling 17-Jul..29-Jul 07:39Z, against a
# `claim_writer` guard merged 31-Jul 00:52Z with zero overlaps since. A
# precondition a book cannot ever clear is a retirement, not a precondition.
#
# Evaluating a precondition over a DIFFERENT sample from the bars is also the
# (hq) defect one layer down: rule and data describing different books.
# --------------------------------------------------------------------------
def _carry_rows(store, monkeypatch, overlap_days_before_era, n_clean=40):
    """A carry ledger with ONE same-pair overlap at a chosen offset from the
    declared era, plus enough clean closes to be gradeable."""
    era_iso = g.POLICY_ERA[g.era_base(CARRY)][0]
    era_d = _dt.datetime.fromisoformat(era_iso).replace(tzinfo=_dt.timezone.utc)

    def at(days, hour=0):
        return (era_d + _dt.timedelta(days=days, hours=hour)).isoformat()

    rows = []
    for i in range(n_clean):        # clean, well inside the era, distinct pairs
        rows.append({"bot": CARRY, "profit_abs": 2.0, "profit_ratio": 0.02,
                     "open_ts": at(1 + i, 0), "close_ts": at(1 + i, 6)})
    # the overlapping pair: two HYPE holds that intersect by ~9h
    d = -overlap_days_before_era
    rows.append({"bot": CARRY, "pair": "HYPE", "profit_abs": 1.0,
                 "profit_ratio": 0.01, "open_ts": at(d, 0), "close_ts": at(d, 12)})
    rows.append({"bot": CARRY, "pair": "HYPE", "profit_abs": 1.0,
                 "profit_ratio": 0.01, "open_ts": at(d, 3), "close_ts": at(d, 15)})
    monkeypatch.setattr(store, "fetch_paper_trades", lambda limit=2000: rows)
    monkeypatch.setattr(sys, "argv", ["golive_readiness.py", "--min-closes", "5"])
    return rows


def test_an_overlap_BEFORE_the_era_no_longer_blocks(capsys, monkeypatch):
    import bot_pnl_store as store
    _carry_rows(store, monkeypatch, overlap_days_before_era=5)
    g.main()
    out = capsys.readouterr().out
    assert "TWO WRITERS" not in out, (
        "a pooled window that predates the graded era still vetoes the book — "
        "the latch is back, and carry can never be READY again:\n" + out)
    assert "historical overlap(s) predate this era" in out, (
        "the historical pooling stopped being REPORTED — it must stay visible "
        "forever, it just must not veto forever:\n" + out)


def test_an_overlap_INSIDE_the_era_still_blocks(capsys, monkeypatch):
    """The detector must not be weakened. An ongoing duplicate writes recent
    trades, and recent trades ARE the era."""
    import bot_pnl_store as store
    _carry_rows(store, monkeypatch, overlap_days_before_era=-3)   # i.e. +3 days
    g.main()
    out = capsys.readouterr().out
    assert "TWO WRITERS" in out, "an in-era overlap must still block:\n" + out
    assert "READY: none" in out


def test_the_alltime_reading_is_still_published(capsys, monkeypatch):
    """Published beside the graded verdict so a consumer can ask either
    question. `two_writers` decides promotion; the all-time count is history."""
    import bot_pnl_store as store
    saved = {}
    _carry_rows(store, monkeypatch, overlap_days_before_era=5)
    monkeypatch.setattr(store, "save_state", lambda k, v: saved.setdefault(k, v))
    monkeypatch.setattr(store, "save_history", lambda k, v: True)
    monkeypatch.setattr(sys, "argv", ["golive_readiness.py", "--min-closes", "5",
                                      "--publish"])
    g.main()
    capsys.readouterr()
    integ = saved["golive-readiness"]["books"][CARRY]["integrity"]
    assert integ["two_writers"] is False, integ
    assert integ["same_pair_overlaps"] == 0, integ
    assert integ["same_pair_overlaps_alltime"] == 1, (
        "the all-time reading was dropped — a real past pooling became "
        "invisible: " + str(integ))
    assert integ["latest_overlap"], "recency (for fleet_immune) must survive"


def test_a_book_with_NO_era_is_unaffected(capsys, monkeypatch):
    """With no declared era the two samples are identical, so this change is a
    no-op for every book but the ones that have one."""
    import bot_pnl_store as store
    bot = "lighter-dislocation-lshadow"       # asserted era-less elsewhere here
    assert g.era_epoch_for(bot) == (None, None, None)
    rows = []
    for i in range(8):
        rows.append({"bot": bot, "profit_abs": 1.0, "profit_ratio": 0.01,
                     "open_ts": f"2026-07-{2 + i:02d}T00:00:00+00:00",
                     "close_ts": f"2026-07-{2 + i:02d}T06:00:00+00:00"})
    rows.append({"bot": bot, "pair": "HYPE", "profit_abs": 1.0, "profit_ratio": 0.01,
                 "open_ts": "2026-07-02T00:00:00+00:00",
                 "close_ts": "2026-07-02T12:00:00+00:00"})
    rows.append({"bot": bot, "pair": "HYPE", "profit_abs": 1.0, "profit_ratio": 0.01,
                 "open_ts": "2026-07-02T03:00:00+00:00",
                 "close_ts": "2026-07-02T15:00:00+00:00"})
    monkeypatch.setattr(store, "fetch_paper_trades", lambda limit=2000: rows)
    monkeypatch.setattr(sys, "argv", ["golive_readiness.py", "--min-closes", "5"])
    g.main()
    out = capsys.readouterr().out
    assert "TWO WRITERS" in out, (
        "an era-less book must behave exactly as before — all its trades are "
        "its graded sample:\n" + out)
