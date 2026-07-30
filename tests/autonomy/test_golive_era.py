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

import pytest

pytestmark = pytest.mark.autonomy

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "scripts"))

import golive_readiness as g          # noqa: E402

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
    assert iso == "2026-07-17", iso
    assert "62.03" in why and "0.91" in why, (
        "the declaration must quote the era split it rests on")
    assert "accrual" in why.lower()


# --------------------------------------------------------------------------
# 2. Keyed on the OPEN, not the close.
# --------------------------------------------------------------------------

def test_a_trade_that_straddles_the_boundary_is_excluded():
    """Opened under the old basis, closed under the new one. It accrued in BOTH,
    so it describes neither era — and its close date would smuggle it in."""
    ep, _, _ = g.era_epoch_for(CARRY)
    assert g.in_era("2026-07-16T12:00", ep, _p) is False, (
        "a pre-era OPEN must be excluded however late it closed")
    assert g.in_era("2026-07-17T00:00", ep, _p) is True, "the boundary is inclusive"


def test_the_era_is_read_off_open_ts_in_the_grading_loop():
    """The wiring, not the arithmetic. `in_era` could be perfect and the loop
    could still pass it the CLOSE stamp — the exact shape of the repo's
    'the selftest proves the arithmetic and not the CALL SITE' trap."""
    src = (_ROOT / "scripts/golive_readiness.py").read_text()
    assert 'in_era(r.get("open_ts")' in src, (
        "the grading loop must key the era on the trade's OPEN stamp")


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
    "perps-funding-lighter-lshadow",     # the fleet's frontrunner AFTER this fix
    "lighter-ticket-taker-lighter",      # real money
    "lighter-ticket-taker-lshadow",
    "pm-gillard-lshadow",
    "freqtrade-mum-lshadow",
])
def test_an_undeclared_book_still_grades_all_time(bot):
    assert g.era_epoch_for(bot) == (None, None, None), (
        f"{bot} gained a policy era — that changes its published verdict and "
        "needs its own declaration and measurement")


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
        assert "-lshadow" not in base and "-lighter" not in base, (
            f"{base} is keyed with a suffix — era_epoch_for strips it, so this "
            "entry can never match a ledger row")


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
    rows = []
    for i in range(40):                       # 40 closes, all BEFORE the era
        rows.append({"bot": CARRY, "profit_abs": 3.0, "profit_ratio": 0.01,
                     "open_ts": f"2026-07-1{i % 5}T00:00:00+00:00",
                     "close_ts": f"2026-07-1{i % 5}T06:00:00+00:00"})
    for i in range(3):                        # 3 closes inside it
        rows.append({"bot": CARRY, "profit_abs": -0.1, "profit_ratio": -0.0003,
                     "open_ts": f"2026-07-2{i}T00:00:00+00:00",
                     "close_ts": f"2026-07-2{i}T06:00:00+00:00"})
    # ...and ONE STRADDLER: opened under the old basis, closed well inside the
    # era. This row is what makes the count below discriminating — key the era
    # on the close stamp and it becomes "4 of 44", which is the bug.
    rows.append({"bot": CARRY, "profit_abs": 9.0, "profit_ratio": 0.03,
                 "open_ts": "2026-07-15T00:00:00+00:00",
                 "close_ts": "2026-07-25T00:00:00+00:00"})
    monkeypatch.setattr(store, "fetch_paper_trades", lambda limit=2000: rows)
    monkeypatch.setattr(sys, "argv", ["golive_readiness.py", "--min-closes", "10"])
    g.main()
    out = capsys.readouterr().out
    assert CARRY in out, (
        "an era'd book with a thin era vanished from the report instead of "
        "showing dark bars — a demotion must be readable")
    assert "era 2026-07-17" in out, "the report does not say it scoped the sample"
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
    assert bot_learn.ERA_START.get("perps-funding-carry") == "2026-07-17T00:00"
    assert bot_learn.era_epoch_for("perps-funding-carry-lshadow") is not None


def test_the_two_era_tables_do_not_CONTRADICT_each_other():
    """Two organs, two tables, one book. They may cover different sets — the
    brain's era is about hypothesis generation and the gate's about promotion
    eligibility — but where BOTH declare a book they must agree, or the fleet
    reasons about two different histories of the same ledger and neither reader
    can tell which one they are looking at."""
    import bot_learn
    for base, (iso, _why) in g.POLICY_ERA.items():
        brain = bot_learn.ERA_START.get(base)
        if brain is None:
            continue
        assert brain.startswith(iso), (
            f"{base}: the go-live gate scopes from {iso} and the brain from "
            f"{brain} — same ledger, two different books")


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
         "era": {"since": "2026-07-17", "why": "the accrual basis changed",
                 "closes_in_era": era["n"], "closes_all_time": alltime["n"]},
         "alltime": g.book_payload(alltime)}
    return b


def test_the_card_says_a_book_was_graded_on_part_of_its_ledger(monkeypatch):
    """`n40` beside a book whose row reports 65 closes is unreadable without
    this. The chip is the only thing tying the bars to the sample they came from.
    """
    out = _card({CARRY: _era_book()}, monkeypatch)
    assert ">era 07-17</span>" in out, out[:400]
    assert "40 of 65 closes" in out, "the chip must quote both counts"


def test_the_card_carries_the_all_time_reading_it_replaced(monkeypatch):
    """Withdrawing credit silently is how a demotion looks like a bug. The
    tooltip has to show what the pooled sample WOULD have said."""
    out = _card({CARRY: _era_book()}, monkeypatch)
    assert "All-time would read" in out, out[:600]


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
