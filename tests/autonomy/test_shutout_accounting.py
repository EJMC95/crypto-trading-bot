#!/usr/bin/env python3
"""[2026-08-27 (vm)] NOTHING COUNTED WHAT THE LIVE RAILS COST.

MEASURED 27-Aug on `freqtrade-georgia-lighter`, the fleet's real-money
directional row: `scan.entries_shut: "protections_locked"` beside
`entry_vetoes.locked_until: 2026-08-27T11:45:14Z`. ONE lockout, live, with no
history behind it — and `entry_vetoes` carried `notional_cap_skips`,
`brain_floored` and `fleet_long_veto` and NO halt counter at all. So on the
three books holding actual money, nobody could state how many evidence-days
the rails have taken, in either direction: an unmeasured rail cannot be
defended under I19 and cannot be loosened under it either.

WHAT THIS FILE PINS, in descending order of what it costs if it breaks:

1. **NO COUNTER REACHES THE ENTRY PATH.** `test_no_rails_counter_reaches_the
   _entry_path` walks the AST of the `if entries_ok:` block and of every
   decision node in the module, and refuses any of the new names. A counter
   that grows a consumer becomes a gate; on real money that is the whole risk
   of this change, and a substring grep is not a wiring test.
2. **THE BUCKETS SUM TO THE TOTAL.** An hour the four declared causes cannot
   explain lands in `unattributed` and is VISIBLE. A total quietly larger than
   its own parts under-reports what a rail costs — the direction that argues
   for keeping a rail nobody has priced.
3. **A DARK SERIES IS NOT A ZERO.** `lockout_hours_30d: None` and a
   zero-filled dict are opposite facts (I1 at counter scale), and the second
   one reads as *measured, the rails cost nothing*.

THE SEAM. There is no DATABASE_URL under pytest, so these tests inject at
`bot_pnl_store.save_history` / `.fetch_state_history` — the two functions
`snapshot_census` and `census_window` call by name, and the narrowest seam
that leaves every line of the code under test running for real. Nothing here
stubs `rails_cost`, `snapshot_census` or `census_window`, and every rollup
below is read back out of rows the REAL publisher wrote (rule 3): the census
payloads come from `rails_cost` itself, never from a dict that "looks like"
one. `test_the_stored_row_is_the_publishers_own_shape` pins that identity.
"""
import ast
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import bot_pnl_store as store            # noqa: E402
import lighter_avo_live_bot as A         # noqa: E402

SRC = ROOT / "lighter_avo_live_bot.py"
TREE = ast.parse(SRC.read_text())

HOUR = 3600.0


# --------------------------------------------------------------------- seam

class FakeHistory:
    """bot_state_history at the save/fetch seam, with a controllable clock.

    Replays `fetch_state_history`'s own documented contract — NEWEST FIRST,
    [{"ts": iso, "payload": dict}], limit-sliced — so the reader under test
    parses exactly what the real reader hands it. The clock is settable
    because the whole point of the rollup is a SPAN: rows all stamped `now`
    span 0.0 hours and every duty cycle would read 0.0, which is the honest
    answer for one instant and a useless fixture."""

    def __init__(self):
        self.rows = []                   # [(key, epoch, payload)]
        self.now = time.time()

    def save(self, key, payload):
        self.rows.append((key, self.now, payload))
        return True

    def fetch(self, key, limit=800):
        import datetime as dt
        got = sorted((r for r in self.rows if r[0] == key),
                     key=lambda r: r[1], reverse=True)
        return [{"ts": dt.datetime.fromtimestamp(
                     ts, dt.timezone.utc).isoformat(), "payload": p}
                for _k, ts, p in got[:int(limit)]]


@pytest.fixture
def hist(monkeypatch):
    fh = FakeHistory()
    monkeypatch.setattr(store, "save_history",
                        lambda key, payload: fh.save(key, payload))
    monkeypatch.setattr(store, "fetch_state_history",
                        lambda key, limit=800: fh.fetch(key, limit))
    return fh


def drive(fh, causes, spacing_h=1.0, seen=None):
    """Run `rails_cost` once per entry in `causes` (None = the book was open),
    one `spacing_h` apart, ending AT the fake clock's `now`. Returns the LAST
    rollup — i.e. the one the row would have published on that loop."""
    seen = {} if seen is None else seen
    base = fh.now
    fh.now = base - (len(causes) - 1) * spacing_h * HOUR
    out = {}
    for i, cause in enumerate(causes):
        t = fh.now
        # reason mirrors the loop's own contract: a bucket carries a reason, an
        # OPEN loop carries neither (`shut_cause` returns (None, None)).
        out = A.rails_cost(
            "test-book:rails", t, "2026-08-27", cause, cause,
            0.0, cause == "daily_halt", seen)
        if i < len(causes) - 1:
            fh.now = t + spacing_h * HOUR
    return out


# ------------------------------------------------- 1) the brief's own drive

def test_a_three_hour_lock_reads_as_three_shut_hours_today(hist):
    """Drive the publisher with a synthetic lock 3h out: `hours_shut_today`
    must carry it. This is the number that did not exist — georgia published
    the lock's ISO stamp and nothing that could be added up or compared."""
    t = hist.now
    out = A.rails_cost("test-book:rails", t, "2026-08-27", "slguard",
                       "protections_locked", t + 3 * HOUR, False, {})
    assert out["hours_shut_today"] >= 3, out
    assert out["lock_pending_h"] == pytest.approx(3.0, abs=0.01), out
    assert out["shut_now"] == "slguard"


def test_hours_shut_today_is_a_floor_never_a_fabricated_zero(hist,
                                                             monkeypatch):
    """A dark series degrades to the lock-only reading and SAYS so. It must
    never degrade to 0.0 — "the rails cost nothing today" is a measurement,
    and this one would be invented."""
    monkeypatch.setattr(store, "fetch_state_history",
                        lambda key, limit=800: [])
    t = hist.now
    out = A.rails_cost("test-book:rails", t, "2026-08-27", "maxdd",
                       "protections_locked", t + 5 * HOUR, False, {})
    assert out["today_basis"] == "lock_only"
    assert out["hours_shut_today"] == pytest.approx(5.0, abs=0.01)
    assert out["lockout_hours_30d"] is None
    assert out["halt_days_30d"] is None
    assert out["entries_shut_reason_30d"] is None


def test_a_daily_halt_is_shut_until_the_utc_day_rolls(hist):
    """The halt's own release is the UTC day roll — the module's rule at the
    top of the loop — so a halted book with no lock still owes hours."""
    t = hist.now
    out = A.rails_cost("test-book:rails", t, "2026-08-27", "daily_halt",
                       "halted_today", 0.0, True, {})
    expect = ((int(t) // 86400 + 1) * 86400 - t) / HOUR
    assert out["hours_shut_today"] >= expect - 0.01, out
    assert out["lock_pending_h"] == 0.0        # no lock — the HALT owes this


# --------------------------------------------------- 2) the buckets balance

def test_the_cause_buckets_sum_to_the_total(hist):
    """THE ACCOUNTING PROPERTY. Five loops an hour apart: two `daily_halt`,
    one `slguard`, two open. 2 of 5 loops over a 4h span is 1.6h of halt."""
    out = drive(hist, ["daily_halt", None, "slguard", None, "daily_halt"])
    lk = out["lockout_hours_30d"]
    assert lk["loops"] == 5 and lk["span_h"] == pytest.approx(4.0, abs=0.01)
    parts = [lk[c] for c in A.SHUT_CAUSES + (A.SHUT_UNATTRIBUTED,)]
    assert sum(parts) == pytest.approx(lk["total"], abs=1e-9), lk
    assert lk["daily_halt"] == pytest.approx(1.6, abs=0.01), lk
    assert lk["slguard"] == pytest.approx(0.8, abs=0.01), lk
    assert lk["maxdd"] == 0.0 and lk["cooldown"] == 0.0


def test_an_unattributed_hour_is_visible_not_silently_dropped(hist):
    """The kill switch is not one of the four causes, and an hour it shut the
    book must still appear. A total that exceeds its own parts is how a rail's
    cost gets under-reported."""
    out = drive(hist, ["daily_halt", None, None, None])
    hist.now += HOUR
    out = A.rails_cost("test-book:rails", hist.now, "2026-08-27",
                       *A.shut_cause(True, False, hist.now, 0.0, None,
                                     None, {}),
                       0.0, False, {})
    lk = out["lockout_hours_30d"]
    assert lk[A.SHUT_UNATTRIBUTED] > 0, lk
    parts = [lk[c] for c in A.SHUT_CAUSES + (A.SHUT_UNATTRIBUTED,)]
    assert sum(parts) == pytest.approx(lk["total"], abs=1e-9), lk
    assert out["entries_shut_reason_30d"]["kill_switch"] == 1, out


def test_the_reason_histogram_counts_every_shut_vocabulary_word(hist):
    """`entries_shut_reason_30d` is the histogram of the loop's OWN reason
    vocabulary, so "the cap turned it away" and "the venue was unreadable"
    stop being the same shut."""
    drive(hist, ["daily_halt", "slguard", "daily_halt"])
    h = A.rails_cost("test-book:rails", hist.now, "2026-08-27", None, None,
                     0.0, False, {})["entries_shut_reason_30d"]
    assert h == {"daily_halt": 2, "slguard": 1}, h


def test_halt_days_counts_DAYS_not_loops(hist):
    """40 shut loops is one day or forty, and the difference is the whole
    argument. The day edge is carried by the series, not inferred from it."""
    seen = {}
    for _ in range(6):
        hist.now += 600
        out = A.rails_cost("test-book:rails", hist.now, "2026-08-27",
                           "slguard", "protections_locked", 0.0, False, seen)
    assert out["halt_days_30d"]["slguard"] == 1, out["halt_days_30d"]
    assert out["halt_days_30d"]["days_any"] == 1, out["halt_days_30d"]
    for _ in range(3):                       # the day rolls
        hist.now += 600
        out = A.rails_cost("test-book:rails", hist.now, "2026-08-28",
                           "slguard", "protections_locked", 0.0, False, seen)
    assert out["halt_days_30d"]["slguard"] == 2, out["halt_days_30d"]


def test_two_rails_on_one_day_do_not_make_two_days(hist):
    """`days_any` is its own counter and is NOT the sum of the parts — a day
    that hits two rails is one day. Summing them would double-count exactly
    the days a struggling book has the most of."""
    seen = {}
    out = A.rails_cost("test-book:rails", hist.now, "2026-08-27", "slguard",
                       "protections_locked", 0.0, False, seen)
    hist.now += 600
    out = A.rails_cost("test-book:rails", hist.now, "2026-08-27",
                       "daily_halt", "halted_today", 0.0, True, seen)
    d = out["halt_days_30d"]
    assert d["slguard"] == 1 and d["daily_halt"] == 1, d
    assert d["days_any"] == 1, d


# ------------------------------------------------------- 3) dark != nothing

def test_an_empty_series_publishes_None_never_a_zero_filled_rollup(hist,
                                                                   monkeypatch):
    monkeypatch.setattr(store, "fetch_state_history",
                        lambda key, limit=800: [])
    out = A.rails_cost("test-book:rails", hist.now, "2026-08-27", None, None,
                       0.0, False, {})
    assert out["lockout_hours_30d"] is None
    assert out["entries_shut_reason_30d"] is None


def test_a_measured_window_with_nothing_shut_publishes_zeros_not_None(hist):
    """The mirror, and it is why None is meaningful: a book that ran and was
    never shut publishes an EMPTY histogram and zero hours. Measured-nothing
    and no-data must be different byte-strings in BOTH directions."""
    out = drive(hist, [None, None, None])
    assert out["lockout_hours_30d"]["total"] == 0.0
    assert out["entries_shut_reason_30d"] == {}


def test_it_never_raises_on_junk(hist):
    """Telemetry in a real-money loop degrades, never throws (rule 5)."""
    for bad in (None, "not-a-number", float("nan")):
        out = A.rails_cost("test-book:rails", bad, "2026-08-27", "slguard",
                           "protections_locked", bad, False, None)
        assert isinstance(out, dict) and "hours_shut_today" in out


# ------------------------------------------------- 4) which rail, and why

@pytest.mark.parametrize("args,expect", [
    # kill_armed, halted, t_now, locked_until, lock_cause, entries_shut, verdicts
    ((True, True, 100.0, 200.0, "maxdd", "protections_locked", {}),
     (A.SHUT_UNATTRIBUTED, "kill_switch")),          # kill wins over all
    ((False, True, 100.0, 200.0, "maxdd", None, {}),
     ("daily_halt", "halted_today")),                # halt beats the lock
    ((False, False, 100.0, 200.0, "slguard", "protections_locked", {}),
     ("slguard", "protections_locked")),
    ((False, False, 100.0, 200.0, "maxdd", "protections_locked", {}),
     ("maxdd", "protections_locked")),
    ((False, False, 300.0, 200.0, "maxdd", None, {}), (None, None)),
])
def test_shut_cause_precedence_is_the_loops_own_order(args, expect):
    assert A.shut_cause(*args) == expect


def test_a_failed_halt_READ_is_not_charged_to_the_daily_rail():
    """`halt_unreadable` fails the entry gate closed, correctly — but it is a
    Postgres blip, not the rail. Charging it to `daily_halt` would inflate the
    one number an argument about that rail will use. Unknown degrades to "I
    cannot attribute this", never to a guess."""
    assert A.shut_cause(False, False, 100.0, 0.0, None,
                        "halt_unreadable", {}) == \
        (A.SHUT_UNATTRIBUTED, "halt_unreadable")


def test_an_unknown_lock_cause_is_unattributed_never_a_guess():
    assert A.shut_cause(False, False, 100.0, 200.0, "who_knows",
                        "protections_locked", {})[0] == A.SHUT_UNATTRIBUTED


def test_cooldown_is_claimed_only_when_every_evaluated_coin_was_cooling():
    """Conservative by construction: one coin cooling while the rest were
    signal-less is the book WORKING, and calling that a rail shutting the book
    would put hours on a bucket that never held it shut."""
    all_cool = {"BTC": "cooldown", "ETH": "cooldown"}
    assert A.shut_cause(False, False, 1.0, 0.0, None, None, all_cool) == \
        ("cooldown", "cooldown")
    mixed = {"BTC": "cooldown", "ETH": "no_signal"}
    assert A.shut_cause(False, False, 1.0, 0.0, None, None, mixed) == \
        (None, None)
    assert A.shut_cause(False, False, 1.0, 0.0, None, None, {}) == (None, None)


# ------------------------------------------- 5) the lock reports its rail

def test_entries_lock_names_the_rail_and_keeps_the_gates_own_number():
    """The refactor's whole risk: the ts the GATE reads must not move. Both
    numbers are derived from the strategy's OWN protections (read, not
    retyped), so a protections change follows and a wrong one still fails."""
    tf_s = A._interval_ms(A.S.tf) / 1000.0
    sg = A.S.protections["slguard"]
    t = 1_000_000.0
    stops = [{"ts": t - 60, "pnl": -1.0, "stop": True}] * sg["trades"]
    ts, cause = A.entries_lock(stops, t, 62.8)
    assert cause == "slguard"
    assert ts == pytest.approx(t + sg["stop"] * tf_s)
    assert A.entries_lock([], t, 62.8) == (0.0, None)


def test_the_maxdd_rail_reports_itself(hist):
    """The drawdown branch, on the LIVE baseline denominator — a $63 book, so
    a $20 trough is 32% against the 20% bar."""
    dd = A.S.protections["maxdd"]
    t = 1_000_000.0
    closed = [{"ts": t - 60, "pnl": -20.0, "stop": False}] + \
             [{"ts": t - 60, "pnl": 0.0, "stop": False}] * (dd["trades"] - 1)
    ts, cause = A.entries_lock(closed, t, 62.8)
    assert cause == "maxdd" and ts > t


# ---------------------------------------- 6) flat is not dark (the I1 half)

@pytest.mark.parametrize("eq,ntl,expect", [
    (230.0, 350.0, "measured"),
    (230.0, 0.0, "flat"),            # georgia + mum on 27-Aug: FLAT, not dark
    (None, 350.0, "equity_dark"),
    (230.0, None, "notional_dark"),  # open_notional() raised
    (0.0, 350.0, "equity_zero"),
])
def test_basket_move_state_separates_flat_from_dark(eq, ntl, expect):
    assert A.basket_move_state(eq, ntl) == expect


def test_the_basket_move_VALUE_is_unchanged_by_the_state_field():
    """Publish-only: the state field is a SIBLING. The value's own None (and
    the arithmetic behind it) is untouched — pinned by reading the source, so
    a future edit to the expression has to face this test."""
    src = SRC.read_text()
    assert "round(DAILY_LOSS_LIMIT * eq / _open_ntl, 4)" in src
    assert "if (eq and _open_ntl) else None" in src


# ------------------------------------ 7) THE ONE THAT MATTERS: no new gate

COUNTERS = {                      # the published field names
    "shut_now", "shut_reason", "hours_shut_today", "hours_shut_basis",
    "lockout_hours_30d", "halt_days_30d", "entries_shut_reason_30d",
    "basket_move_now_state",
}
SYMBOLS = {                       # everything (vm) introduced in code
    "SHUT_CAUSES", "SHUT_UNATTRIBUTED", "RAILS_CENSUS_BOT", "shut_cause",
    "shut_day_edge", "basket_move_state", "rails_cost", "_rails", "_rc",
    "_shut_now", "_shut_why", "lock_cause",
}
#: The four functions that OWN this telemetry. They may branch on their own
#: inputs; nothing else may branch on any of it.
OWNERS = {"shut_cause", "shut_day_edge", "basket_move_state", "rails_cost"}
#: `_selftest` is exempt for the opposite reason: asserting on a published
#: counter is what a test DOES, and a test cannot become a gate. It is named
#: here rather than folded into OWNERS so the exemption stays one rule wide
#: (the (mz) lesson: an exemption that grows is a guard that stops guarding).
DECISION_EXEMPT = OWNERS | {"_selftest"}


def _fn(name, tree=TREE):
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and n.name == name:
            return n
    raise AssertionError("function not found: " + name)


def _names(node):
    """Every identifier and string constant in a subtree."""
    out = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Name):
            out.add(n.id)
        elif isinstance(n, ast.Attribute):
            out.add(n.attr)
        elif isinstance(n, ast.arg):
            out.add(n.arg)
        elif isinstance(n, ast.Constant) and isinstance(n.value, str):
            out.add(n.value)
    return out


def _entries_block():
    """The `if entries_ok:` subtree inside main() — the entry path itself."""
    for n in ast.walk(_fn("main")):
        if isinstance(n, ast.If) and isinstance(n.test, ast.Name) \
                and n.test.id == "entries_ok":
            return n
    raise AssertionError("`if entries_ok:` not found — the entry path moved")


def test_no_rails_counter_reaches_the_entry_path():
    """THE TEST THIS CHANGE EXISTS UNDER. Every name (vm) introduced, checked
    against the AST of the block that actually opens real-money positions. A
    counter that grows a consumer becomes a gate, and a grep for the string
    would pass on a payload key while missing an `if` — so this walks nodes."""
    used = _names(_entries_block())
    # PREMISE FIRST ((po)): an empty output is not a negative result until the
    # check has been seen to look at something. These three are the entry
    # path's own furniture — the order call, the cap and the sizing.
    assert {"market_open", "notional_ok", "brain_clip_for"} <= used, \
        "the entry-path scan found nothing to scan — the block moved"
    leak = sorted((COUNTERS | SYMBOLS) & used)
    assert leak == [], f"rails telemetry reached the entry path: {leak}"


def test_the_entry_gate_expression_is_the_same_five_terms():
    """`entries_ok` is the gate itself. It must still read the lock's TS —
    the refactor that gave `entries_lock` a cause must not have moved what the
    gate compares."""
    for n in ast.walk(_fn("main")):
        if isinstance(n, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "entries_ok"
                for t in n.targets):
            expr = ast.unparse(n.value)
            break
    else:
        raise AssertionError("entries_ok assignment not found")
    assert "t0 >= locked_until" in expr, expr
    assert not (COUNTERS | SYMBOLS) & _names(ast.parse(expr)), expr


def test_no_decision_anywhere_in_the_module_reads_a_rails_counter():
    """Wider than the entry path: no `if`, `while`, ternary, comparison or
    boolean anywhere in the file may branch on a published counter — that is
    what "a counter that grows a consumer becomes a gate" means in code. The
    four owner functions are exempt on their OWN inputs, and `_selftest`
    because a test asserting on a counter cannot become a gate."""
    owned = set()
    for name in DECISION_EXEMPT:
        owned |= {id(x) for x in ast.walk(_fn(name))}
    bad = []
    for node in ast.walk(TREE):
        tests = []
        if isinstance(node, (ast.If, ast.While, ast.IfExp)):
            tests = [node.test]
        elif isinstance(node, (ast.Compare, ast.BoolOp)):
            tests = [node]
        for t in tests:
            if id(t) in owned:
                continue
            hit = COUNTERS & _names(t)
            if hit:
                bad.append((getattr(node, "lineno", "?"), sorted(hit)))
    assert bad == [], f"a rails counter is being branched on: {bad}"


def test_the_publisher_writes_its_own_namespace_not_the_scan_census():
    """`<row>:rails` — pooling the shut series and a future scan census under
    one key would be the (hp) two-writers shape at counter scale."""
    assert A.RAILS_CENSUS_BOT == A.BOT_ROW + ":rails"


def test_the_stored_row_is_the_publishers_own_shape(hist):
    """Rule 3 made executable: the keys read back are the keys `rails_cost`
    wrote, through the REAL `snapshot_census` — never an invented fixture."""
    A.rails_cost("test-book:rails", hist.now, "2026-08-27", "slguard",
                 "protections_locked", 0.0, False, {})
    key, _ts, row = hist.rows[0]
    assert key == "test-book:rails:census", key
    assert row["shut"] == 1
    assert row["shut_by.slguard"] == 1 and row["shut_by.daily_halt"] == 0
    assert row["reason.protections_locked"] == 1
    assert row[store.CENSUS_DROPPED_KEY] == 0, row   # nothing uncountable
    assert set(row) - {store.CENSUS_DROPPED_KEY} == {
        "shut", "day_first.any", "day_first.slguard",
        "reason.protections_locked"} | {
        "shut_by." + c for c in A.SHUT_CAUSES + (A.SHUT_UNATTRIBUTED,)}, row


def test_the_telemetry_refresh_never_adds_a_loop_to_the_census():
    """`_publish_row(snapshot=False)` is the (us) between-passes refresh. If it
    snapshotted, the denominator would grow ~5x while the shut loops did not,
    and every duty cycle would silently read a fifth of the truth."""
    body = ast.unparse(_fn("_publish_row"))
    assert "if snapshot:" in body
    idx = body.index("rails_cost(")
    guard = body.rindex("if snapshot:", 0, idx)
    assert "_rails[0] = rails_cost(" in body[guard:idx + 40], body[guard:idx]


def test_it_is_publish_only():
    """No lever, no order, no gate — asserted of the new surface's own source
    (rule 6), not of the diff, so it keeps holding after the next edit."""
    seg = "\n".join(ast.unparse(_fn(n)) for n in sorted(OWNERS))
    for forbidden in ("get_lever", "write_levers", "market_open",
                      "market_close", "publish_paper_trade", "kill_check"):
        assert forbidden not in seg, forbidden


def test_a_store_with_no_census_api_still_publishes_the_lock_floor(hist,
                                                                   monkeypatch):
    """THE ORDER IS THE FAIL-SAFE. `snapshot_census` / `census_window` are
    (vm)-new in bot_pnl_store, so an image shipped before them raises
    AttributeError inside `rails_cost` — and the lock-only floor is computed
    BEFORE that call precisely so the row still says how long this book is
    shut, instead of degrading to a fabricated 0.0."""
    monkeypatch.delattr(store, "snapshot_census")
    t = hist.now
    out = A.rails_cost("test-book:rails", t, "2026-08-27", "slguard",
                       "protections_locked", t + 4 * HOUR, False, {})
    assert out["hours_shut_today"] == pytest.approx(4.0, abs=0.01), out
    assert out["today_basis"] == "lock_only"
    assert out["lockout_hours_30d"] is None
