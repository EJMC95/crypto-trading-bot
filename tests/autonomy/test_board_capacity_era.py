"""[2026-08-26] THE CAPACITY AUTHOR WAS WIDENING A BOOK ITS OWN GRADER REFUSES.

THE INCIDENT, measured on the live bus the day this was written. `fleet_tuning`
carried

    carry.max_positions = 18   lane lighter-books   set_by evidence-board
    reason: "SATURATED at 18/16, MTM +$63.11"
    evidence: "perps-funding-carry-lshadow: open=18 closed=104"

— a ratchet 12 -> 14 -> 16 -> 18 authored by `evidence_board.synthesize_books`'s
SATURATED branch. Three things were true at the same moment:

  * FAULT A — WRONG SAMPLE. The authorising `+$63.11` is `pnl_abs`, which is
    ALL-TIME. The sample the GO-LIVE GATE itself uses to describe 🌾 carry as
    it runs today read **n=13, mean -0.218%/trade, t=-4.82**, five of six bars
    dark, `ready: false`. The `(hc)` era precondition sits in FRONT of the six
    bars and had never reached this actuator. `(nc)` additionally records ~$13
    of that all-time accrual as PHANTOM (pre-basis-fix over-accrual), so the
    number was partly out of era AND partly not real.

  * FAULT B — THE TRIGGER FIRES ON A DRAINING BOOK. `open_n >= cap` is also
    true when the cap was ratcheted DOWN under open positions. Carry held 18
    against a published cap of 16 and the bot's guard is
    `len(positions) < MAX_POSITIONS`, so it could not enter: an overhang
    draining, not a book asking for room.

  * SUPPLY, not capacity. Carry's own census read `eligible: 0` of 228
    scanned. The binding constraint was the one the rail was not moving (I18).

`(hs)` had already added the MTM profit term so saturation ALONE could not
widen; it fixed WHICH TRIGGER fires and never WHICH SAMPLE the profit term
reads, nor that saturation is also true while draining. This is that lesson one
layer deeper.

WHAT THESE TESTS PIN, and each is a term that must be the SOLE reason in some
case or it is decoration:
  1. the live carry case as it stood is REFUSED;
  2. a book genuinely AT cap, era-positive and with supply STILL WIDENS — the
     positive control, without which "refuses everything" would pass;
  3. a dark / stale / bookless / unstamped grader payload refuses (fail-closed);
  4. a draining book (open > cap) refuses even when era-positive;
  5. the era rule is the GRADER's by IDENTITY — no copy lives in the board.

Every golive fixture here is PUBLISHER-BUILT: real rows -> the real
`golive_readiness.stats()` -> the real `golive_readiness.book_payload()`. The
board reads a `bars` map it does not own, so a hand-written fixture would only
test the fixture (the (hj) class). The `bot_pnl` rows carry the field names
their real publishers emit — `extra.caps.max_positions` and `extra.scan` from
`funding_carry_bot.scan_census`.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import evidence_board as eb              # noqa: E402
import fleet_tuning as tn                # noqa: E402
import scripts.golive_readiness as gr    # noqa: E402

CARRY = "perps-funding-carry-lshadow"
CAP_LEVER = "carry.max_positions"
NOW = 2_000_000.0          # the board's clock is epoch seconds


class _Rail:
    """The growth-rail registry, real cages and real clamp, injectable value."""

    LEVERS = tn.LEVERS
    vals = {}

    @staticmethod
    def get_lever(name, default, now_ts=None):
        return _Rail.vals.get(name, default)

    @staticmethod
    def clamp(name, value):
        return tn.clamp(name, value)


@pytest.fixture(autouse=True)
def _clean_rail():
    _Rail.vals = {}
    yield
    _Rail.vals = {}


def series(n, mean, t):
    """`n` per-trade percents whose real `stats()` reads this mean and this t.

    Built by solving rather than typed, so the incident fixture below can be
    ASSERTED to reproduce 🌾 carry's published n/mean/t instead of being a
    plausible-looking hand-written stand-in. `t = mean / (sd/sqrt(n))` with sd
    the population sd `stats()` computes, and a half-up / half-down series of
    deviation `d` around the mean has population sd `d*sqrt((n - n%2)/n)`.
    """
    import math
    sd = abs(mean) * math.sqrt(n) / abs(t)
    d = sd / math.sqrt((n - n % 2) / n)
    out = [mean + (d if i % 2 else -d) for i in range(n - n % 2)]
    return out + [mean] * (n % 2)


def golive_payload(pcts, bot=CARRY, age_s=0.0, span_days=40.0, stamp=True):
    """A `golive-readiness` payload built by the GRADER, not by hand.

    `pcts` are per-trade percents oldest-first; the row shape
    `(pnl_pct, pnl_abs, closed_at)` is `golive_readiness.stats`'s own contract.
    """
    t0 = datetime(2026, 6, 1, tzinfo=timezone.utc)
    step = timedelta(days=span_days / max(1, len(pcts) - 1))
    rows = [(p, p * 10.0, t0 + i * step) for i, p in enumerate(pcts)]
    out = {"ttl_sec": gr.TTL_SEC, "bar_names": list(gr.BAR_NAMES),
           "books": {bot: gr.book_payload(gr.stats(rows))}}
    if stamp:
        out["updated"] = datetime.fromtimestamp(NOW - age_s,
                                                timezone.utc).isoformat()
    return out


# noisy on purpose: a constant series gives t ~ 1e16 and would hide a sign or
# formatting defect in the published tag.
GL_GOOD = golive_payload([0.012, 0.008] * 20)
GL_BAD = golive_payload([-0.012, -0.008] * 20)
# 🌾 carry's REAL era-scoped sample the day of the incident, as the go-live
# grader published it: n=13, mean -0.218%/trade, t=-4.82, over 21.7 days.
GL_CARRY_LIVE = golive_payload(series(13, -0.00218, -4.82), span_days=21.7)


def test_the_incident_fixture_reproduces_the_published_numbers():
    """A fixture that does not reproduce the incident cannot test the fix.
    These three are read off `golive-readiness` on the day of the widening."""
    rec = GL_CARRY_LIVE["books"][CARRY]
    assert rec["n"] == 13
    assert rec["mean_pct"] == pytest.approx(-0.218, abs=0.001)
    assert rec["t"] == pytest.approx(-4.82, abs=0.01)
    assert rec["days"] == pytest.approx(21.7, abs=0.05)
    assert rec["bars"]["mean"] is False and rec["bars_passed"] <= 1


def carry_row(open_n=16, cap=16, pnl_abs=63.11, eligible=3, census=True):
    """A `bot_pnl` row shaped like the one 🌾 carry actually publishes."""
    extra = {"caps": {"max_positions": cap, "enter_apr": 0.2,
                      "min_vol": 1_000_000.0, "persist_h": 12.0}}
    if census:
        extra["scan"] = {"scanned": 228, "held": open_n, "cold": 193,
                         "thin": 14, "waiting": 3, "noncrypto": 0,
                         "eligible": eligible}
    return [{"bot": CARRY, "open_trades": open_n, "closed_trades": 104,
             "pnl_abs": pnl_abs, "extra": extra}]


def author(rows, golive_state, prop=None, now=NOW):
    return eb.synthesize_books(rows, {}, prop or {}, now, tuning_mod=_Rail,
                               golive_state=golive_state)


def held_items(items):
    return [i for i in items if i.get("direction") == "hold"]


# --------------------------------------------------------------------------
# 1. THE INCIDENT
# --------------------------------------------------------------------------
def test_the_live_carry_case_is_refused():
    """open 18 / cap 16, all-time +$63.11, era n=13 mean -0.218% t=-4.82,
    census eligible 0 — the exact state that authored carry.max_positions=18."""
    levers, items = author(carry_row(open_n=18, cap=16, eligible=0),
                           GL_CARRY_LIVE)
    assert levers == {}, (
        "the live 🌾 carry case must be REFUSED; this widening reached the "
        f"bus as carry.max_positions=18: {levers}")
    held = held_items(items)
    assert held and held[0]["lever"] == CAP_LEVER, items
    # the operator must be able to see WHY without re-deriving it
    assert "18" in held[0]["msg"] and "16" in held[0]["msg"], held[0]["msg"]


def test_the_era_sample_is_what_refuses_carry_not_the_overhang_alone():
    """Fault A must stand on its own: put carry exactly AT its cap with real
    supply and a positive MTM, and the grader's own era record still refuses.

    Without this, fixing only the drain term would have re-authorised the
    ratchet the moment the book's overhang cleared."""
    levers, items = author(carry_row(open_n=16, cap=16, eligible=3),
                           GL_CARRY_LIVE)
    assert levers == {}, levers
    msg = held_items(items)[0]["msg"]
    assert "era record NOT positive" in msg, msg
    assert "-0.218" in msg and "-4.82" in msg, (
        "the refusal must publish the era numbers, not just say no: " + msg)


def test_all_time_profit_alone_no_longer_authorises_a_widening():
    """The authorising number itself: +$63.11 all-time, era negative."""
    ok, why = eb.era_capacity_claim(GL_CARRY_LIVE, CARRY, NOW)
    assert ok is False and "NOT positive" in why, why
    # ...while the SAME row with a positive era record does widen, so the
    # term discriminates rather than blanket-refusing.
    levers, _ = author(carry_row(), GL_GOOD)
    assert levers.get(CAP_LEVER, {}).get("value") == 14, levers


# --------------------------------------------------------------------------
# 2. THE POSITIVE CONTROL — required, or "refuse everything" would pass
# --------------------------------------------------------------------------
def test_a_book_at_cap_with_a_positive_era_and_real_supply_still_widens():
    levers, items = author(carry_row(open_n=16, cap=16, eligible=3), GL_GOOD)
    step = tn.LEVERS[CAP_LEVER]["step"]
    want = tn.LEVERS[CAP_LEVER]["env_default"] + step
    assert levers.get(CAP_LEVER, {}).get("value") == want, levers
    assert [i for i in items if i["direction"] == "expand"], items
    reason = levers[CAP_LEVER]["reason"]
    # the reason must name all three terms it cleared, so a later reader can
    # audit the authorisation instead of trusting the word SATURATED
    assert "AT CAP" in reason and "eligible" in reason and "era" in reason, reason


def test_the_widening_is_exactly_one_step_and_stops_at_the_cage():
    _Rail.vals = {CAP_LEVER: tn.LEVERS[CAP_LEVER]["hi"]}
    levers, _ = author(carry_row(open_n=16, cap=16), GL_GOOD)
    assert levers == {}, "at the registry ceiling the author proposes nothing"


def test_a_hurting_verdict_still_outranks_a_fully_qualified_widening():
    levers, _ = author(carry_row(), GL_GOOD,
                       prop={"verdicts": {CAP_LEVER: {"verdict": "hurting"}}})
    assert levers == {}, levers
    # ...and HELPING must not be read as a block (symmetry)
    levers, _ = author(carry_row(), GL_GOOD,
                       prop={"verdicts": {CAP_LEVER: {"verdict": "helping"}}})
    assert levers.get(CAP_LEVER, {}).get("value") == 14, levers


# --------------------------------------------------------------------------
# 3. FAIL-CLOSED: absence of evidence never authorises exposure
# --------------------------------------------------------------------------
@pytest.mark.parametrize("state,tag", [
    (None, "dark (the default)"),
    ({}, "empty"),
    ({"books": {}}, "no books, no stamp"),
    (golive_payload([0.012, 0.008] * 20, stamp=False), "no `updated` stamp"),
    (golive_payload([0.012, 0.008] * 20, age_s=gr.TTL_SEC + 1), "stale"),
    (golive_payload([0.012, 0.008] * 20, age_s=-7200), "future-stamped"),
    (golive_payload([0.012, 0.008] * 20, bot="a-different-book"), "book absent"),
    ({"updated": "not-a-date", "books": {CARRY: {"bars": {}}}}, "junk stamp"),
])
def test_an_unusable_grader_payload_refuses_the_widening(state, tag):
    levers, _ = author(carry_row(), state)
    assert levers == {}, f"a {tag} golive payload must not widen: {levers}"


def test_a_truncated_bar_map_is_unreadable_not_permission():
    """A payload whose `bars` is missing a name the grader publishes is a
    foreign or truncated payload — not a pass."""
    good = golive_payload([0.012, 0.008] * 20)
    assert good["books"][CARRY]["bars"]["mean"] is True
    good["books"][CARRY]["bars"].pop("halves")
    ok, why = eb.era_capacity_claim(good, CARRY, NOW)
    assert ok is False and "bar map" in why, why


@pytest.mark.parametrize("bad", [1, "true", "True", None, 0])
def test_only_a_real_json_true_on_the_mean_bar_authorises(bad):
    """`bars` values are JSON bools. Anything else is unreadable, and
    unreadable must not read as permission (a truthy 1 or "true" would)."""
    state = golive_payload([0.012, 0.008] * 20)
    state["books"][CARRY]["bars"]["mean"] = bad
    ok, _ = eb.era_capacity_claim(state, CARRY, NOW)
    assert ok is False, f"bars['mean']={bad!r} must not authorise a widening"


@pytest.mark.parametrize("field", ["n", "mean_pct", "t"])
# `True` is a MUTATION SURVIVOR from the first round: `_num`'s bool guard was
# unreachable from a None-only list, yet `format(True, '+.3f')` renders
# `+1.000` — a bool would print as a plausible NUMBER in the refusal an
# operator reads, which is worse than printing nothing (I8).
@pytest.mark.parametrize("junk", [None, True])
def test_a_junk_field_in_the_graded_record_refuses_without_crashing(field, junk):
    """The grader publishes `None` for every number on an n<2 sample. The
    organ that renders the refusal must survive that, and still refuse."""
    state = golive_payload([0.012, 0.008] * 20)
    state["books"][CARRY][field] = junk
    ok, why = eb.era_capacity_claim(state, CARRY, NOW)
    assert "n/a" in why or ok is True     # rendered, not raised
    state["books"][CARRY]["bars"]["mean"] = False
    ok, why = eb.era_capacity_claim(state, CARRY, NOW)
    assert ok is False and "n/a" in why, (
        f"{field}={junk!r} must render as n/a, never as a number: {why}")


def test_a_dark_grader_and_a_stale_one_are_not_the_same_refusal():
    """MUTATION SURVIVOR, first round: dropping `or not golive_state` from the
    first guard left every test green, because an empty payload is refused a
    second time downstream by `publish_is_fresh`. Refusing for the right reason
    is not a detail here — DARK (the organ never published this key) and STALE
    (it published and stopped) are different operator actions (I1/I8), and the
    hold item is where an operator reads which one it is.
    """
    for dark in (None, {}):
        ok, why = eb.era_capacity_claim(dark, CARRY, NOW)
        assert ok is False and "dark" in why, (dark, why)
        assert "fresh" not in why, (
            "an empty/absent payload must read DARK, not stale — the second "
            f"guard catching it is defence in depth, not the diagnosis: {why}")
    # ...and the three OTHER liveness failures each keep their own name, so the
    # four are not one indistinguishable refusal. `{"books": {}}` is NOT dark:
    # a payload that exists and carries no stamp is unproven, per I1.
    for unproven in ({"books": {}},
                     golive_payload([0.012, 0.008] * 20, stamp=False),
                     golive_payload([0.012, 0.008] * 20,
                                    age_s=gr.TTL_SEC + 1)):
        ok, why = eb.era_capacity_claim(unproven, CARRY, NOW)
        assert ok is False and "not proven fresh" in why, why


def test_an_unreadable_clock_refuses_instead_of_falling_back_to_wall_time():
    """MUTATION SURVIVOR, first round: replacing `return False, "unreadable
    clock"` with `now_dt = None` survived every test, because the fixtures are
    stamped at the board's epoch (NOW = 2_000_000) and so read stale against
    the machine's clock either way — both paths refused, for different reasons.

    The hazard only shows on a payload that IS fresh by wall time: the mutant
    then judges freshness by the MACHINE's clock instead of the board's cycle
    clock and AUTHORISES the widening. The era claim must be judged on the
    clock the caller handed it, or a junk `now_ts` silently changes which
    authority decides.
    """
    live = golive_payload([0.012, 0.008] * 20)
    live["updated"] = datetime.now(timezone.utc).isoformat()   # fresh NOW
    # sanity: it is genuinely a payload that would authorise on its own clock
    assert eb.era_capacity_claim(live, CARRY, datetime.now(timezone.utc)
                                 .timestamp())[0] is True
    for junk in ("not-a-number", None, float("nan"), object()):
        ok, why = eb.era_capacity_claim(live, CARRY, junk)
        if junk is None:
            continue          # None means "no clock supplied", not a bad one
        assert ok is False and "clock" in why, (junk, why)


def test_the_grader_module_constants_are_read_not_retyped():
    """MUTATION SURVIVOR, first round: `GOLIVE_KEY = golive.KEY` replaced by
    the literal `"golive-readiness"` passed everything, because the identity
    test compares by EQUALITY and a correct copy is equal today. That is the
    exact drift the module's own comment names for the TTL — (mw) moved
    43200 and a literal would have missed it — and the KEY has the same
    failure mode: the board would fetch and read a key the grader no longer
    publishes, going permanently dark on a fail-CLOSED branch, silently.

    So the claim is STRUCTURAL (AST), not a value comparison: each constant
    must be an attribute read off the imported grader, never a Constant.
    """
    import ast
    src = (Path(__file__).resolve().parents[2] / "evidence_board.py").read_text()
    want = {"GOLIVE_KEY": "KEY", "GOLIVE_MAX_AGE_S": "TTL_SEC"}
    seen = {}
    for node in ast.walk(ast.parse(src)):
        if not isinstance(node, ast.Assign):
            continue
        for tgt in node.targets:
            if isinstance(tgt, ast.Name) and tgt.id in want:
                seen[tgt.id] = node.value
    assert set(seen) == set(want), f"constants missing: {set(want) - set(seen)}"
    for name, attr in want.items():
        val = seen[name]
        assert isinstance(val, ast.Attribute), (
            f"{name} is retyped as a literal instead of read from the grader "
            f"— import the constant, never restate it: {ast.dump(val)}")
        assert val.attr == attr and isinstance(val.value, ast.Name), ast.dump(val)
        assert val.value.id == "golive", ast.dump(val)


def test_a_thin_sample_the_grader_cannot_grade_never_authorises():
    """n<2 -> `bar_map` returns every bar False and every number None. That is
    the grader saying "I cannot tell", and it must not read as permission."""
    thin = golive_payload([0.01])
    assert thin["books"][CARRY]["n"] == 1
    assert thin["books"][CARRY]["mean_pct"] is None
    levers, _ = author(carry_row(), thin)
    assert levers == {}, levers


def test_the_default_is_dark_so_a_forgetful_caller_widens_nothing():
    """The parameter defaults to None: a caller that does not hand over the
    grader's payload gets no widening rather than the old all-time behaviour."""
    levers, _ = eb.synthesize_books(carry_row(), {}, {}, NOW, tuning_mod=_Rail)
    assert levers == {}, levers


# --------------------------------------------------------------------------
# 4. THE DRAIN TERM
# --------------------------------------------------------------------------
def test_a_draining_book_refuses_even_when_everything_else_is_green():
    levers, items = author(carry_row(open_n=18, cap=16, eligible=5), GL_GOOD)
    assert levers == {}, "open > cap is an overhang draining, not demand"
    msg = held_items(items)[0]["msg"]
    assert "OVERHANG" in msg and "18" in msg and "16" in msg, msg


def test_at_cap_and_over_cap_are_not_the_same_state():
    """The whole content of the drain term: identical rows apart from one
    open position, opposite verdicts."""
    at_cap, _ = author(carry_row(open_n=16, cap=16), GL_GOOD)
    over, _ = author(carry_row(open_n=17, cap=16), GL_GOOD)
    assert at_cap.get(CAP_LEVER) and not over, (at_cap, over)


def test_below_the_cap_is_not_saturation_at_all():
    levers, items = author(carry_row(open_n=12, cap=16), GL_GOOD)
    assert levers == {}, levers
    assert not held_items(items), "a book with free slots is not a hold item"


# --------------------------------------------------------------------------
# 5. THE SUPPLY TERM (I18)
# --------------------------------------------------------------------------
def test_a_supply_bound_book_is_not_widened():
    """`eligible: 0` of 228 scanned — the binding constraint is supply."""
    levers, items = author(carry_row(eligible=0), GL_GOOD)
    assert levers == {}, levers
    assert "supply" in held_items(items)[0]["msg"], items


def test_a_book_with_no_census_cannot_demonstrate_demand():
    levers, items = author(carry_row(census=False), GL_GOOD)
    assert levers == {}, levers
    msg = held_items(items)[0]["msg"]
    assert "supply" in msg and "no census" in msg, msg
    # and the refusal is actionable: it names what to publish (I8)
    assert eb.BOOK_SUPPLY_KEY in held_items(items)[0]["proposal"]


@pytest.mark.parametrize("val", [
    None, True, False, "3", -1, float("nan"),
    # MUTATION SURVIVORS, first round — both guards below were unreachable
    # from this list, so deleting either left the suite green:
    2.5,                 # a FRACTION is not a count; `int(2.5)` would read 2
    float("inf"), float("-inf"),   # and `int(inf)` RAISES, taking the organ
                                   # down rather than merely widening wrongly
])
def test_an_unreadable_eligible_count_is_unknown_not_supply(val):
    rows = carry_row()
    rows[0]["extra"]["scan"]["eligible"] = val
    levers, _ = author(rows, GL_GOOD)
    assert levers == {}, f"eligible={val!r} must not authorise a widening"
    # ...and it must REFUSE, never raise: `book_supply` is called with no
    # try/except around it, so a junk count that throws kills the whole author.
    assert eb.book_supply(rows[0])[0] is None, val


def test_the_second_census_field_is_actually_reachable():
    """MUTATION SURVIVOR, first round: dropping `BOOK_SUPPLY_KEY not in cens`
    from the loop condition survived, because every fixture puts `eligible`
    inside the FIRST field. `BOOK_CENSUS_FIELDS` is a preference ORDER, and a
    fallback nothing can reach is not a fallback — a book publishing `scan`
    without a count and `census` with one would read as supply-unknown forever.
    """
    assert eb.BOOK_CENSUS_FIELDS == ("scan", "census"), eb.BOOK_CENSUS_FIELDS
    rows = carry_row(eligible=5)
    rows[0]["extra"]["scan"].pop("eligible")          # first field: no count
    rows[0]["extra"]["census"] = {"eligible": 5}      # second field carries it
    assert eb.book_supply(rows[0]) == (5, "census"), eb.book_supply(rows[0])
    levers, _ = author(rows, GL_GOOD)
    assert levers.get(CAP_LEVER, {}).get("value") == 14, levers


def test_the_census_field_names_are_the_publishers_own():
    """`extra.scan` / `eligible` are `funding_carry_bot.scan_census`'s names,
    not names invented here — a consumer reading a key its publisher does not
    emit is the (hj) class, and it is silent."""
    import funding_carry_bot as fcb
    census = fcb.scan_census({}, {}, {}, 0.0, 8.0, 0.2)
    assert eb.BOOK_SUPPLY_KEY in census, census
    assert "scan" in eb.BOOK_CENSUS_FIELDS
    # and the accessor reads it out of a row shaped the way the bot publishes
    assert eb.book_supply(carry_row(eligible=7)[0]) == (7, "scan")


# --------------------------------------------------------------------------
# 6. THE ERA RULE IS THE GRADER'S, BY IDENTITY
# --------------------------------------------------------------------------
def test_the_board_imports_the_era_rule_and_does_not_reimplement_it():
    assert eb.golive.era_rows is gr.era_rows
    assert eb.golive.bar_map is gr.bar_map
    assert eb.GOLIVE_KEY == gr.KEY
    assert eb.GOLIVE_MAX_AGE_S == gr.TTL_SEC, (
        "a retyped TTL drifts — (mw) moved this 86400 -> 43200 and a copy "
        "here would have missed it")


def test_the_board_defines_no_era_or_gate_constant_of_its_own():
    """AST, not a substring scan: a second copy of the rule is a second rule.
    Assignments only — reading the imported names is exactly what we want."""
    import ast
    src = (Path(__file__).resolve().parents[2] / "evidence_board.py").read_text()
    banned = {"POLICY_ERA", "ERA_START", "GOLIVE_MIN_DAYS", "GOLIVE_MIN_CLOSES",
              "GOLIVE_MIN_T", "GOLIVE_MAX_DD", "BAR_NAMES"}
    assigned = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name):
                    assigned.add(tgt.id)
        elif isinstance(node, (ast.AnnAssign,)) and isinstance(node.target, ast.Name):
            assigned.add(node.target.id)
    assert not (assigned & banned), (
        f"evidence_board re-declares gate/era constants: {assigned & banned}")


def test_the_grader_key_is_actually_fetched_by_main():
    """A consumer whose key is not on the batch fetch list is INERT — the (hh)
    lesson. Fail-closed here means an unfetched key freezes the branch, which
    is silent in the other direction and just as wrong."""
    import ast
    src = (Path(__file__).resolve().parents[2] / "evidence_board.py").read_text()
    tree = ast.parse(src)
    found = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "_keys"
                for t in node.targets):
            names = {n.id for n in ast.walk(node.value)
                     if isinstance(n, ast.Name)}
            consts = {c.value for c in ast.walk(node.value)
                      if isinstance(c, ast.Constant)}
            found = "GOLIVE_KEY" in names or gr.KEY in consts
    assert found, "`golive-readiness` is not on evidence_board's fetch list"
    # ...and the payload is passed THROUGH to the author, not fetched and dropped
    assert "golive_state=_g(GOLIVE_KEY)" in src


def test_the_grader_ships_in_the_image_that_runs_this_organ():
    """BORN-DARK, and `audit_image_imports` CANNOT cover this one — MEASURED.

    The board's new dependency is a DOTTED repo-local import
    (`import scripts.golive_readiness`). Replacing it with
    `import scripts.definitely_not_a_module` leaves `audit_image_imports.py`
    GREEN, so its pass says nothing about this import and a missing COPY would
    ship silently — the exact class that guard exists for, one dot deeper.
    (The guard's blind spot is reported, not fixed here: it is another
    session's file.)

    So the containment is asserted directly, off the guard's OWN reconstruction
    of the image's file set — `image_contents` returns a 4-TUPLE, which is the
    `(iw)` trap that produced a silently EMPTY map once already.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
    import audit_image_imports as aii
    _top, files, _copies, _unparsed = aii.image_contents("Dockerfile.freqtrade")
    assert "evidence_board.py" in files, sorted(files)[:20]
    assert "scripts/golive_readiness.py" in files, (
        "evidence_board imports scripts.golive_readiness and the freqtrade "
        "image no longer COPYs it — the organ would fall back to nothing")
    # `scripts/` carries no __init__.py, so the import rides Python's implicit
    # namespace packages off PYTHONPATH=/freqtrade. Pin that, because adding
    # an __init__.py elsewhere or moving the file breaks it silently.
    assert not (Path(__file__).resolve().parents[2] / "scripts" /
                "__init__.py").exists()
    assert gr.__name__ == "scripts.golive_readiness", gr.__name__


def test_the_capacity_branch_reads_no_all_time_only_authorisation():
    """`book_mtm_pnl` is KEPT (it closes I9's open-position blind spot) but it
    may no longer be the only term: the era claim and the supply read must both
    be called inside the same branch."""
    import ast
    src = (Path(__file__).resolve().parents[2] / "evidence_board.py").read_text()
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == "synthesize_books")
    called = {n.func.id for n in ast.walk(fn)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert {"book_mtm_pnl", "era_capacity_claim", "book_supply"} <= called, called
