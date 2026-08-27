"""[2026-08-26] THE DECLARED POLICY-PARITY WAIVER — judge v2.0 rung R3.

🔮 georgia is the fleet's closest promotion pair (live 42 / shadow 67 economic
closes in the trailing window) and she sat one rung from judgeable on a single
field: her live host scans via `lighter_avo_live_bot.diversified_order` while
her shadow scans in list order, so `scan_order` diverges and R3 read
`policy_mismatch` forever.

The divergence is REAL. What the measurement says is that on THIS pair it is
INERT: scan order can only change which candidate is taken while the book is
CHOOSING — at or near its cap — and time-weighted occupancy from each arm's own
ledger puts the shadow AT CAP 0.6% of the time (208 episodes, cap 5, flat
66.3%, mean 0.56/5) and the live arm AT CAP 5.0% (47 episodes, cap 5, flat
51.3%, mean 0.90/5). Both arms are SIGNAL-limited, not slot-limited.

So `fleet_bus.JUDGED_PAIRS["georgia"]["policy_waived"]` declares the field with
that measurement and a revisit condition, in the `BORN_DARK_OK` / `UNJUDGED_OK`
idiom. THREE properties are the whole safety of it, and each has a test here
that a mutation reddens:

  1. WAIVED ≠ HIDDEN. The field stays in `policy_fields`, the judge keeps
     detecting the divergence, and republishes it on the pair entry as
     `policy_waived` with both arms' values — including when a LATER rung
     blocks the pair. A waiver that swallows the difference is how this class
     returns.
  2. NARROW. 🙏 avo's live arm was measured at its ceiling 21.7% of the time
     ((sr)) — an order of magnitude more often — so avo and 👩 mum carry no
     waiver and must keep reading `policy_mismatch` on the identical
     divergence. That is the control this file exists to hold.
  3. NEVER OVER DARKNESS. A waived field that either arm cannot be READ on is
     `parity_unreadable`, not waived. Assumed-equal is exactly the F1 handicap
     the Stage-0 census was built to close, and a waiver must not smuggle it
     back in.

AND THE WAIVER HAS A MIRROR, in section 6 below. The same two arms carry a
SECOND entry-policy divergence — the shadow throttles entries per clock hour,
the live host declares that it does not — which is measured MATERIAL and which
NEITHER host stamps, so the parity rung compared None to None and read EQUAL.
`policy_stamp_required` turns that absence into a block that names the stamp
work and self-closes when both publishers ship it. The two declarations are
opposites on purpose and the tests hold them apart: `scan_order` is waived on
measurement and does not block; the throttle is not waived and does.


Fixtures are PUBLISHER-SHAPED and PUBLISHER-ORDERED: rows carry the keys
`bot_pnl_store.fetch_paper_trades` really emits (`close_ts`, `extra`, …) and
arrive NEWEST-FIRST, because that fetch is `ORDER BY closed_at DESC NULLS
LAST`. Each arm gets MORE rows than `_latest_policy_stamp`'s 30-row window with
the interesting stamp at the NEWEST end and a differently-stamped tail behind
it — a one-row-per-key fixture cannot test a window, and that exact gap bit
this census twice in two days ((tj), (ts)).
"""
import ast
import os
import sys
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import fleet_bus  # noqa: E402
import experiment_judge as ej  # noqa: E402

#: More than `_latest_policy_stamp`'s `look` window, so the slice is exercised.
LOOK = 30
N_ROWS = 40

GEORGIA = fleet_bus.JUDGED_PAIRS["georgia"]
#: georgia's SECOND entry-policy divergence — the shadow throttles entries per
#: clock hour and the live host does not — declared in
#: `policy_stamp_required` because NEITHER host stamps it today.
THROTTLE = "max_entries_per_hour"
#: The waiver fixtures stamp the throttle ALIGNED on both arms on purpose: it
#: is a separate, UNWAIVED block with its own tests below, and a fixture that
#: diverged on two fields at once could not tell which one produced the
#: verdict.
LIVE_POL = {"strategy": "daytrader-15m", "venue": "lighter_live",
            "stoploss": -0.05, "roi": {"0": 0.02}, "sides": ["long"],
            "scan_order": "diversified", THROTTLE: 3}
SHADOW_POL = dict(LIVE_POL, venue="lighter_shadow", scan_order="list")


def _now():
    """WALL CLOCK. `_pair_precheck._fresh` reads `now_ts()` and ignores the
    `now` it is handed, so a fixture stamped off a frozen constant ages past
    the 3xTTL bar as the session runs and every pair collapses to
    `live_row_dark` — a fixture whose verdict depends on when the suite runs
    is worse than no fixture."""
    return datetime.now(timezone.utc)


def _close(bot, age_h, policy=None):
    """One ledger row in the shape `fetch_paper_trades` REALLY returns.

    Note `close_ts` — that fetch normalises `closed_at` to `close_ts` and every
    other consumer in the judge reads `close_ts`. Written the publisher's way
    rather than the reader's, per the (hj) rule.
    """
    r = {"bot": bot, "pair": "SPY/USDC", "profit_abs": 0.42,
         "profit_ratio": 0.004, "enter_tag": "long", "exit_reason": "roi",
         "duration_min": 61.0, "is_open": False, "venue": "lighter",
         "open_rate": 100.0, "close_rate": 100.4,
         "open_ts": (_now() - timedelta(hours=age_h + 1)).isoformat(),
         "close_ts": (_now() - timedelta(hours=age_h)).isoformat(),
         "extra": {}}
    if policy is not None:
        r["extra"]["policy"] = dict(policy)
    return r


def _ledger(live_bot, shadow_bot, live_pol, shadow_pol,
            tail_pol=None, n=N_ROWS):
    """`n` rows per arm, NEWEST FIRST, with the policy under test on the newest
    close and `tail_pol` on everything behind it.

    The tail is the point: it is stamped with a divergence on a NON-waived
    field, so a reader that scored the OLDEST rows (the pre-(ts) `[-look:]`)
    would return `policy_mismatch` on `stoploss` instead of the verdict under
    test. That makes the window and the ordering load-bearing here rather than
    decorative.
    """
    tail_pol = tail_pol if tail_pol is not None else dict(shadow_pol,
                                                          stoploss=-0.99)
    rows = []
    for bot, newest in ((live_bot, live_pol), (shadow_bot, shadow_pol)):
        rows.append(_close(bot, 1, newest))
        rows += [_close(bot, 2 + i, tail_pol) for i in range(n - 1)]
    rows.sort(key=lambda r: r["close_ts"], reverse=True)   # the fetch's order
    return rows


def _row(bot, max_open=5, age_s=30):
    """A `bot_pnl` row as `fetch_bot_pnl` really returns it — `updated_at` as
    ISO, never a precomputed `age_sec` (the (tj) trap).

    [(uw)] `ttl_sec: 900` is gone: this claimed publisher fidelity while
    carrying a key `fetch_bot_pnl` does not build (`ttl_sec` occurs zero times
    in bot_pnl_store.py — the table has no such column). `_fresh` read
    `3 * (row.ttl_sec or 900)`, so the fixture drove the per-row branch and
    production drove the fallback: mutating the live bar `900 -> 1` left the
    whole suite green. The bar is now `PAIR_ROW_STALE_S` and this drives it."""
    return {"bot": bot, "status": "online", "equity": 1000.0,
            "pnl_abs": 0.0, "pnl_pct": 0.0, "open_trades": 1,
            "closed_trades": 52, "wins": 30, "losses": 22,
            "updated_at": (_now() - timedelta(seconds=age_s)).isoformat(),
            "extra": {"max_open": max_open}}


def _precheck(pspec, rows, bot_rows):
    return ej._pair_precheck("georgia", pspec, rows, bot_rows,
                             _now().timestamp())


def _pair(pspec, live_pol, shadow_pol, live_cap=5, shadow_cap=5):
    lb, sb = pspec["live_bot"], pspec["shadow_bot"]
    return _precheck(pspec,
                     _ledger(lb, sb, live_pol, shadow_pol),
                     [_row(lb, live_cap), _row(sb, shadow_cap)])


# ---------------------------------------------------------------------------
# 1. THE WAIVER CLEARS R3 AND THE PAIR REACHES idle
# ---------------------------------------------------------------------------

def test_georgia_passes_r3_on_the_waived_field_and_reaches_idle():
    """The live divergence, driven through the REAL precheck: scan_order
    diversified vs list, caps 5 and 5, both arms stamped."""
    st = _pair(GEORGIA, LIVE_POL, SHADOW_POL)
    assert st.get("phase") == "idle", st
    assert "unjudgeable" not in st, st
    # non-degenerate: the idle entry is fully built, not an empty shell
    assert isinstance(st.get("power"), dict), st
    assert st["power"]["live"]["n"] >= 1, st["power"]


def test_the_waived_divergence_is_republished_not_swallowed():
    """A waiver that HIDES the difference is how this class comes back. The
    entry must name the field and carry BOTH arms' values plus the reason."""
    st = _pair(GEORGIA, LIVE_POL, SHADOW_POL)
    waived = st.get("policy_waived")
    assert isinstance(waived, dict) and "scan_order" in waived, st
    w = waived["scan_order"]
    assert w["live"] == "diversified" and w["shadow"] == "list", w
    assert isinstance(w["why"], str) and len(w["why"]) >= 200, w
    # ...and an operator reading the card sees it too: the idle note names it.
    assert "scan_order" in st.get("note", ""), st.get("note")


def test_the_waiver_is_still_reported_when_a_later_rung_blocks():
    """Published BEFORE the capacity rung can return. A pair that stops at R4
    still carries its waiver, or the divergence disappears from the record for
    exactly the pairs someone is about to go fix."""
    st = _pair(GEORGIA, LIVE_POL, SHADOW_POL, live_cap=5, shadow_cap=6)
    assert st["unjudgeable"]["reason"] == "capacity_mismatch", st
    assert st.get("policy_waived", {}).get("scan_order", {}) \
        .get("shadow") == "list", st


def test_the_verdict_does_not_depend_on_the_order_the_rows_arrive_in():
    """[(uw)] THE FIXTURES WERE PUBLISHER-SHAPED AND PUBLISHER-ORDERED, AND
    THE SECOND HALF HID A DEAD SORT.

    Every case in this file hands `_pair_precheck` rows already newest-first,
    because that is how `fetch_paper_trades` returns them — so the window came
    out right whether or not `_latest_policy_stamp`'s sort did any work. It
    did none: `_close_rank` read `closed_at`, the DB COLUMN, which that fetch
    normalises to `close_ts` and never emits, so it ranked EVERY real row
    `(False, 0.0)` and the sort was a stable no-op. `(ts)` added that sort
    precisely to make the answer independent of how the caller fetched, and
    with the key wrong it was not.

    Delivered oldest-first, a dead sort scores the TAIL — stamped
    `stoploss=-0.99` by `_ledger` — and the pair reads `policy_mismatch`
    instead of `idle`. So this asserts the verdict, not the plumbing.

    (mutation: `close_ts` -> `closed_at` in `_close_rank` => this reddens)
    """
    lb, sb = GEORGIA["live_bot"], GEORGIA["shadow_bot"]
    rows = _ledger(lb, sb, LIVE_POL, SHADOW_POL)
    bot_rows = [_row(lb, 5), _row(sb, 5)]
    expected = _precheck(GEORGIA, rows, bot_rows)
    assert expected.get("phase") == "idle", expected

    oldest_first = list(reversed(rows))
    # neither the publisher's order nor its exact reverse, so a "fix" that
    # flips the slice to suit one caller cannot satisfy this either
    rotated = rows[len(rows) // 3:] + rows[:len(rows) // 3]
    for label, perm in (("oldest-first", oldest_first), ("rotated", rotated)):
        got = _precheck(GEORGIA, perm, bot_rows)
        assert got.get("phase") == "idle", (label, got)
        assert got.get("unjudgeable") is None, (label, got)
        assert got["stamps"] == expected["stamps"], (label, got["stamps"])
        assert got.get("policy_waived") == expected.get("policy_waived"), label


def test_the_sort_key_reads_the_key_the_publisher_actually_emits():
    """The (hj) rule at its narrowest: `_close_rank` must rank a row that the
    REAL publisher built. A key the publisher never emits degrades silently to
    the NULLS-LAST bucket — no raise, no log, just an inert sort — which is
    why this needs asserting directly rather than through a verdict.

    (mutation: `close_ts` -> `closed_at` in `_close_rank` => this reddens)
    """
    newer = ej._close_rank(_close(GEORGIA["shadow_bot"], 1))
    older = ej._close_rank(_close(GEORGIA["shadow_bot"], 900))
    assert newer[0] is True, ("inert on a publisher-shaped row", newer)
    assert newer > older, (newer, older)
    # a row carrying no close time at all is unorderable, never "newest"
    assert ej._close_rank({"bot": "x", "extra": {}}) == (False, 0.0)


def _publisher_row_keys():
    """The key set `bot_pnl_store.fetch_paper_trades` really constructs, read
    off its own `out.append({...})` literal. Derived from the publisher rather
    than restated here, because a retyped key set is a second copy of the
    contract and drifts exactly like the one that caused (uw)."""
    import bot_pnl_store
    tree = ast.parse(open(bot_pnl_store.__file__).read())
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef)
              and n.name == "fetch_paper_trades")
    keys = set()
    for n in ast.walk(fn):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "append" and n.args
                and isinstance(n.args[0], ast.Dict)):
            keys |= {k.value for k in n.args[0].keys
                     if isinstance(k, ast.Constant) and isinstance(k.value, str)}
    return keys


def _row_keys_read_by(fn_name, rowvar="r"):
    """Every `<rowvar>.get("literal")` inside one judge function.

    Receiver must be a BARE NAME: `(r.get("extra") or {}).get("policy")` is a
    read of the extra SUB-DICT, not of the row, and counting it would make
    this guard cry wolf on every stamp field."""
    tree = ast.parse(open(ej.__file__).read())
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == fn_name)
    return {n.args[0].value for n in ast.walk(fn)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr == "get" and isinstance(n.func.value, ast.Name)
            and n.func.value.id == rowvar and n.args
            and isinstance(n.args[0], ast.Constant)
            and isinstance(n.args[0].value, str)}


#: Judge functions that read a LEDGER row, with the local the row is bound to.
#: Curated, not discovered: adding one is a deliberate act, and every entry
#: here has been checked to consume `fetch_paper_trades` output specifically
#: (not `fetch_bot_pnl` rows, which are a different publisher and shape).
LEDGER_ROW_READERS = (("_close_rank", "r"), ("_latest_policy_stamp", "r"))


def test_every_ledger_key_the_census_reads_is_one_the_publisher_emits():
    """[(uw)] THE CLASS, NOT THE INSTANCE.

    `_close_rank` read `closed_at` — the DB COLUMN — for a day while
    `fetch_paper_trades` normalised it to `close_ts` and emitted no `closed_at`
    at all. Nothing caught it: `.get` on an absent key returns None, so the
    consumer and the publisher can disagree forever in total silence, and the
    fixtures agreed with the CONSUMER so they could not tell either.

    This reads both sides off their own ASTs, so it reddens whichever side
    moves — a `closed_at` retyped into the judge, or a `close_ts` renamed in
    the publisher. The fallback it replaced could only ever have covered the
    first, and only by hiding it.

    (mutation: `close_ts` -> `closed_at` in `_close_rank` => this reddens)
    """
    # THE ROSTER MUST NOT BE EMPTIABLE. A `for` over an empty tuple passes in
    # silence, so shrinking `LEDGER_ROW_READERS` would retire this guard
    # without reddening anything — the "a check that inspects nothing reports
    # clean" class, caught here by mutation on this very test.
    covered = {name for name, _ in LEDGER_ROW_READERS}
    assert {"_close_rank", "_latest_policy_stamp"} <= covered, sorted(covered)
    for name, _ in LEDGER_ROW_READERS:
        assert callable(getattr(ej, name, None)), (name, "no such function")

    emitted = _publisher_row_keys()
    # positive control: the extractor must actually find a real key set, or
    # an empty `emitted` would make every subset check below vacuously true
    assert {"bot", "close_ts", "extra"} <= emitted, sorted(emitted)
    assert "closed_at" not in emitted, (
        "fetch_paper_trades now emits closed_at — the (uw) premise changed, "
        "re-read _close_rank before relaxing this")

    for fn_name, rowvar in LEDGER_ROW_READERS:
        read = _row_keys_read_by(fn_name, rowvar)
        assert read, (fn_name, "extracted no row keys — the AST walk is "
                               "broken or the row variable was renamed")
        assert read <= emitted, (
            fn_name, "reads ledger keys the publisher never emits",
            sorted(read - emitted), "emitted:", sorted(emitted))


def test_an_undeclared_divergence_on_the_same_pair_still_blocks():
    """The waiver is per FIELD, not per pair: georgia diverging on `stoploss`
    — which she does NOT declare — must still read policy_mismatch, naming
    stoploss and not mentioning the waived field as a blocker."""
    st = _pair(GEORGIA, LIVE_POL, dict(SHADOW_POL, stoploss=-0.09))
    assert st["unjudgeable"]["reason"] == "policy_mismatch", st
    assert "stoploss" in st["unjudgeable"]["detail"], st
    assert "'scan_order'" not in st["unjudgeable"]["detail"], st


# ---------------------------------------------------------------------------
# 2. NARROWNESS — the control this file exists to hold
# ---------------------------------------------------------------------------

def test_avo_and_mum_have_no_waiver_and_still_read_policy_mismatch():
    """🙏 avo's live arm sits at its ceiling 21.7% of the time ((sr)) — an
    order of magnitude more often than georgia's 5.0% — so the same field is
    NOT inert there. If a mutation applies georgia's waiver fleet-wide, this
    is what reddens."""
    for pid in ("avo", "mum"):
        pspec = fleet_bus.JUDGED_PAIRS[pid]
        assert not pspec.get("policy_waived"), (
            f"{pid} has grown a waiver — a waiver is a per-pair MEASUREMENT, "
            f"so it needs its own occupancy numbers and its own test row here")
        st = _pair(pspec, LIVE_POL, SHADOW_POL)
        assert st["unjudgeable"]["reason"] == "policy_mismatch", (pid, st)
        assert "scan_order" in st["unjudgeable"]["detail"], (pid, st)
        assert "policy_waived" not in st, (pid, st)


def test_exactly_one_pair_carries_a_waiver_today():
    """A RATCHET, in the `REJECTED_SLEEVES` / `SLEEVE_EXEMPT` idiom: the
    backlog of waived parity may only shrink, and a NEW waiver fails the push
    that adds it until someone writes its measurement down here."""
    waived = {pid for pid, p in fleet_bus.JUDGED_PAIRS.items()
              if p.get("policy_waived")}
    assert waived == {"georgia"}, (
        f"declared parity waivers changed: {sorted(waived)}. A waiver is a "
        f"measured act — add the pair's own at-cap occupancy to its reason "
        f"string and update this ratchet deliberately.")


# ---------------------------------------------------------------------------
# 3. DARKNESS IS NEVER WAIVED
# ---------------------------------------------------------------------------

def test_a_waived_field_missing_from_an_arm_fails_closed():
    """`.get` returns None for "absent" exactly as it does for "null", and
    neither is a measured value. Waiving it would let a stamp that never
    mentions scan_order pass as if the arms had been compared."""
    blind = {k: v for k, v in LIVE_POL.items() if k != "scan_order"}
    st = _pair(GEORGIA, blind, SHADOW_POL)
    assert st["unjudgeable"]["reason"] == "parity_unreadable", st
    assert "scan_order" in st["unjudgeable"]["detail"], st
    assert "policy_waived" not in st, st


def test_a_waived_field_stamped_null_fails_closed_too():
    """The other half of the same shape — present-but-null. A readability
    check that only tests `in stamp` passes this and waives darkness."""
    st = _pair(GEORGIA, dict(LIVE_POL, scan_order=None), SHADOW_POL)
    assert st["unjudgeable"]["reason"] == "parity_unreadable", st
    st = _pair(GEORGIA, LIVE_POL, dict(SHADOW_POL, scan_order=None))
    assert st["unjudgeable"]["reason"] == "parity_unreadable", st


def test_a_falsey_but_real_value_is_readable_and_waivable():
    """The negative control on the readability rule: `0`, `False` and `[]` are
    values an arm can legitimately stamp. A truthiness test would fail the pair
    closed on a REAL reading — safe, wrong, and it trains the operator to
    ignore the state."""
    for falsey in (0, False, []):
        st = _pair(GEORGIA, dict(LIVE_POL, scan_order=falsey), SHADOW_POL)
        assert st.get("phase") == "idle", (falsey, st)
        assert st["policy_waived"]["scan_order"]["live"] == falsey, st


# ---------------------------------------------------------------------------
# 4. A PAIR WITH NO WAIVER IS BYTE-COMPATIBLE WITH THE PRE-WAIVER JUDGE
# ---------------------------------------------------------------------------

#: The genuine PRE-CHANGE spec: neither declaration, and `policy_fields` back
#: to the six fields the two hosts actually stamp today.
NO_WAIVER = dict(
    {k: v for k, v in GEORGIA.items()
     if k not in ("policy_waived", "policy_stamp_required")},
    policy_fields=tuple(f for f in GEORGIA["policy_fields"] if f != THROTTLE))


def test_no_waiver_key_leaves_the_mismatch_detail_byte_identical():
    st = _pair(NO_WAIVER, LIVE_POL, SHADOW_POL)
    assert st["unjudgeable"]["reason"] == "policy_mismatch", st
    assert st["unjudgeable"]["detail"] == (
        "arms diverge on ['scan_order']: "
        "live={'scan_order': 'diversified'} shadow={'scan_order': 'list'}"), st
    assert st["unjudgeable"]["wake_when"] == (
        "the divergence is ported across or declared out of this pair's "
        "policy_fields — a measured act, never a silent default"), st
    assert "policy_waived" not in st, st


def test_no_waiver_key_leaves_the_idle_note_byte_identical():
    """The pre-waiver note, to the character. The waiver clause is appended
    ONLY where a waiver actually fired."""
    st = _pair(NO_WAIVER, LIVE_POL, dict(SHADOW_POL, scan_order="diversified"))
    assert st["phase"] == "idle", st
    assert st["note"] == ("judgeable; no candidate in this pair's queue "
                          "(xp.georgia.*) — the lever wave is v2.1"), st
    assert "policy_waived" not in st, st


# ---------------------------------------------------------------------------
# 5. THE MECHANISM IS GENERAL, AND THE DECLARATIONS ARE REAL
# ---------------------------------------------------------------------------

def test_the_waiver_mechanism_is_not_hardcoded_to_scan_order():
    """A positive control on a DIFFERENT field, injected into a copy of the
    spec — proving the rung reads the declaration rather than the field name
    (the STALE_WRITER_OK lesson: a mechanism tested only on its one live
    instance is a mechanism nobody has seen work)."""
    synthetic = dict(GEORGIA, policy_waived={"roi": "synthetic, test-only"})
    st = _pair(synthetic, LIVE_POL, dict(SHADOW_POL, roi={"0": 0.09},
                                         scan_order="diversified"))
    assert st["phase"] == "idle", st
    assert st["policy_waived"]["roi"]["shadow"] == {"0": 0.09}, st


def test_every_declared_waiver_names_a_field_the_pair_actually_checks():
    """A waiver on a field outside `policy_fields` is a dead declaration: the
    rung never reaches it, so it reads as a live exemption and guards nothing.
    And the field must NOT have been deleted from `policy_fields` to make room
    — deleting it hides the divergence, which is the opposite of the point."""
    for pid, p in fleet_bus.JUDGED_PAIRS.items():
        for field in (p.get("policy_waived") or {}):
            assert field in p["policy_fields"], (
                f"{pid} waives {field!r}, which is not in its policy_fields — "
                f"a waiver must keep the field DETECTED and published")


# ---------------------------------------------------------------------------
# 6. THE WAIVER'S MIRROR — a REQUIRED field neither host stamps must BLOCK
#
# The pair that motivated this: georgia's shadow throttles entries per clock
# hour (MAX_ENTRIES_PER_HOUR=3) and her live host declares that it enforces no
# throttle at all. Measured on the two arms' own ledgers, entries per ACTIVE
# hour are shadow {1:108h, 2:44h, 3:4h} (at-or-over the cap 2.6% of active
# hours) against live {1:16h, 2:5h, 3:3h, 4:1h, 9:1h} (19.2%, reaching NINE) —
# and the shadow's own ledger prices the difference: entry_rank 1 =
# -0.443%/trade (n=24) vs rank 2 = +0.828% (n=9). One arm is rank-censored and
# the other is not, so the paired bar would compare different entry
# populations. NEITHER host stamps it, so the parity rung compares None to None
# and reads EQUAL. These are the tests that stop that from being silence.
# ---------------------------------------------------------------------------

def test_an_unstamped_required_field_blocks_and_names_the_stamp_work():
    """The whole point of the mirror: absent-from-both must not read as
    'the arms agree'."""
    blind_l = {k: v for k, v in LIVE_POL.items() if k != THROTTLE}
    blind_s = {k: v for k, v in SHADOW_POL.items() if k != THROTTLE}
    st = _pair(GEORGIA, blind_l, blind_s)
    assert st["unjudgeable"]["reason"] == "policy_unstamped", st
    d = st["unjudgeable"]["detail"]
    assert THROTTLE in d, d
    # I8 — it names the objects a session must open, both of them
    assert "lighter_family_bot.py" in d and GEORGIA["host_file"] in d, d
    assert "policy_stamp" in st["unjudgeable"]["wake_when"], st
    # ...and it carries the MEASUREMENT, not just the fact
    assert "19.2%" in d and "2.6%" in d, d


def test_the_throttle_divergence_is_not_waived_and_still_blocks():
    """(c) — the pair of assertions that is the whole point: `scan_order` is
    waived and does NOT block; the throttle is measured MATERIAL, carries no
    waiver, and blocks on its value the moment both arms stamp it."""
    st = _pair(GEORGIA, dict(LIVE_POL, **{THROTTLE: None}), SHADOW_POL)
    assert st["unjudgeable"]["reason"] == "policy_mismatch", st
    assert THROTTLE in st["unjudgeable"]["detail"], st
    # the waived field is STILL reported on the same entry — one block does
    # not erase the other's record
    assert st["policy_waived"]["scan_order"]["shadow"] == "list", st
    # and it is genuinely not waived, at the declaration
    assert THROTTLE not in (GEORGIA.get("policy_waived") or {}), (
        "the throttle must never be waived without its own evidence and a "
        "human decision — it is measured MATERIAL, not measured inert")


def test_a_required_field_stamped_null_counts_as_answered():
    """PRESENCE, never truthiness. `None` is the honest stamp for 'this host
    has no such rule' — a host that says so has answered, and the divergence
    then belongs to the parity rung, on its value."""
    st = _pair(GEORGIA, dict(LIVE_POL, **{THROTTLE: None}),
               dict(SHADOW_POL, **{THROTTLE: None}))
    assert st["phase"] == "idle", st          # both say None -> agreed, waived
    assert st["policy_waived"]["scan_order"]["live"] == "diversified", st


def test_a_required_field_stamped_by_only_one_arm_still_blocks():
    """Half-landed stamp work is the dangerous middle: one host ships the
    field and the other has not deployed yet.

    The reason is `policy_mismatch`, not `policy_unstamped`, and that is the
    RIGHT answer rather than an accident — the parity rung now has a real
    difference to report (a value against an absence) and names the field,
    which is more actionable than "somebody has not stamped it". What matters
    for fairness is only that it BLOCKS, and it does, from both directions."""
    for pol_l, pol_s in ((dict(LIVE_POL), {k: v for k, v in SHADOW_POL.items()
                                           if k != THROTTLE}),
                         ({k: v for k, v in LIVE_POL.items() if k != THROTTLE},
                          dict(SHADOW_POL))):
        st = _pair(GEORGIA, pol_l, pol_s)
        assert st["phase"] == "unjudgeable", st
        assert st["unjudgeable"]["reason"] == "policy_mismatch", st
        assert THROTTLE in st["unjudgeable"]["detail"], st


def test_a_pair_with_no_required_declaration_is_unchanged():
    """Byte-compat: the rung is opt-in per pair. avo and mum declare nothing,
    so an unstamped field is invisible to them exactly as it was."""
    for pid in ("avo", "mum"):
        assert not fleet_bus.JUDGED_PAIRS[pid].get("policy_stamp_required")
    st = _pair(NO_WAIVER,
               {k: v for k, v in LIVE_POL.items() if k != THROTTLE},
               {k: v for k, v in SHADOW_POL.items()
                if k not in (THROTTLE, "scan_order")})
    # no waiver, no requirement, scan_order absent from the shadow stamp ->
    # the pre-change judge's own verdict on an absent field: a plain mismatch
    assert st["unjudgeable"]["reason"] == "policy_mismatch", st
    assert "policy_waived" not in st, st


def test_every_required_field_is_in_policy_fields():
    """A required field outside `policy_fields` would be stamped and then
    never compared — the mirror of the dead-waiver failure."""
    for pid, p in fleet_bus.JUDGED_PAIRS.items():
        for field in (p.get("policy_stamp_required") or {}):
            assert field in p["policy_fields"], (
                f"{pid} requires {field!r} to be stamped but never compares "
                f"it — add it to policy_fields or drop the requirement")


def test_no_family_policy_field_is_one_the_publisher_never_stamps():
    """THE CLASS, not the instance — and this test exists because a mutation
    survived without it.

    ANY `policy_fields` entry neither host stamps compares None to None, reads
    EQUAL, and passes the parity rung in silence: the registry then claims to
    police a divergence it structurally cannot see, which is worse than not
    listing the field at all. So every family pair's field must either be
    EMITTED by the real shared builder (`lighter_family_bot.policy_stamp`,
    called here rather than parsed — a fixture that 'looks like' the payload is
    how four of these shipped green) or be DECLARED in
    `policy_stamp_required`, which turns the absence into a block.

    SCOPE, declared: the three family pairs, whose stamps that builder owns.
    💸 farmer's stamp comes from `lighter_funding_bot` and is not this
    builder's to answer for.
    """
    import lighter_family_bot as fb

    class _S:                      # the fields policy_stamp actually reads
        style, stoploss, roi = "daytrader-15m", -0.05, {0: 0.02}

    # [(uv)] the 4th argument is the HOST's answer for its own hourly
    # throttle; None here means "this stub host enforces none".
    emitted = set(fb.policy_stamp(_S(), "lighter_shadow", "list", None))
    assert emitted, "the shared policy_stamp builder emitted nothing"
    for pid, p in fleet_bus.JUDGED_PAIRS.items():
        if p.get("host_file") != "lighter_avo_live_bot.py":
            continue
        required = set(p.get("policy_stamp_required") or {})
        dead = [f for f in p["policy_fields"]
                if f not in emitted and f not in required]
        assert not dead, (
            f"{pid} lists policy_field(s) {dead} that "
            f"lighter_family_bot.policy_stamp never emits and that nothing "
            f"declares required — they compare None to None, read EQUAL, and "
            f"make the registry claim a check it cannot perform. Either stamp "
            f"them at the builder or declare them in policy_stamp_required.")


def test_every_required_field_declaration_carries_its_evidence():
    """An exemption needs a measurement; so does a BLOCK. A required-stamp
    entry that cannot say why is a hold nobody can clear."""
    for pid, p in fleet_bus.JUDGED_PAIRS.items():
        for field, why in (p.get("policy_stamp_required") or {}).items():
            assert isinstance(why, str) and len(why) >= 200, (pid, field)
            assert "%" in why, (pid, field, "no measurement")
            assert "policy_stamp" in why, (
                pid, field, "does not name the stamp work that clears it")


def test_every_declared_waiver_carries_its_measurement_and_a_revisit():
    """The reason string is the whole artifact: an exemption without a number
    and a way out is a snooze, not a decision (the acknowledged-recurrence
    rule)."""
    for pid, p in fleet_bus.JUDGED_PAIRS.items():
        for field, why in (p.get("policy_waived") or {}).items():
            assert isinstance(why, str) and len(why) >= 200, (pid, field)
            low = why.lower()
            assert "at cap" in low, (pid, field, "no occupancy measurement")
            assert "%" in why, (pid, field, "no number")
            assert "revisit" in low, (pid, field, "no way out")
