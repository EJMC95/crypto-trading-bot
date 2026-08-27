"""[2026-08-27 (vm)] `snapshot_census` / `census_window` — the fleet's first
TIME-ACCUMULATED refusal counter.

WHY THIS FILE EXISTS. Measured 27-Aug: not one of the 20 book rows on
/pnl.json publishes a counter that survives its own loop. 🎫 the taker's
`slot_census {offered: 4, slots_full: 4}` — the entire evidence that its
position cap binds — is a sample of n=1 CYCLE, so no widening of `TT_MAX_OPEN`
can ever be priced under I19 and none has ever shipped. The counter is only
worth anything if the read side is HONEST about what it did and did not
measure, so most of what is pinned here is the fail-safe half:

  * empty history returns {} and NOT a zero-filled dict (a fabricated
    `{"slots_full": 0}` reads as *measured, nothing refused* when the truth is
    *no data* — I1 at counter scale);
  * `hours` is the span actually covered, never the span requested;
  * `binding_gate` names a DECLARED refusal and can never name a denominator;
  * a field that could not be counted is COUNTED, not silently discarded.

THE SEAM. There is no DATABASE_URL under pytest (the root conftest strips it,
pinned by tests/autonomy/test_db_unreachable_in_tests.py), so these tests
inject at the `save_history` / `fetch_state_history` module globals — the exact
two functions `snapshot_census` and `census_window` call by name, and the
NARROWEST seam that still leaves every line of the code under test running for
real. Nothing here mocks `snapshot_census` or `census_window` themselves.

The census payloads are PUBLISHER-BUILT: they come out of
`lighter_book_hull_bot.scan_census`, the real gate-order census of a living
book, never a dict that "looks like" one. `test_the_stored_keys_are_the
_publishers_own_keys` pins that identity so this file cannot drift into
testing an invented shape.
"""
import time

import pytest

import bot_pnl_store as store
import lighter_book_hull_bot as hull


H = hull.H
_IN_BAND = 0.10 / H          # 10% TRUE apr — inside hull's [7.82%, 20%) band


def hull_census():
    """One REAL census off the living book's own gate, chosen so a refusal
    bucket (`thin` = 3) is the largest refusal while a DENOMINATOR (`scanned`
    = 5) is larger still — the exact shape that catches a binding_gate which
    ranks totals."""
    fund = {"AAA": {"rate": _IN_BAND, "vol": 1e5},     # thin
            "BBB": {"rate": _IN_BAND, "vol": 1e5},     # thin
            "CCC": {"rate": _IN_BAND, "vol": 1e5},     # thin
            "DDD": {"rate": 0.001 / H, "vol": 5e6},    # below_band
            "EEE": {"rate": _IN_BAND, "vol": 5e6}}     # eligible
    return hull.scan_census(fund, set(), {"EEE": -1e9}, 0.0)


class FakeHistory:
    """Stands in for bot_state_history at the save/fetch seam. Replays rows in
    `fetch_state_history`'s own documented contract — NEWEST FIRST,
    [{"ts": iso, "payload": dict}] — so the reader under test parses exactly
    what the real reader hands it, limit slicing included."""

    def __init__(self):
        self.rows = []          # [(key, epoch, payload)] oldest first

    def save(self, key, payload, at=None):
        self.rows.append((key, time.time() if at is None else at, payload))
        return True

    def fetch(self, key, limit=800):
        import datetime as dt
        got = [r for r in self.rows if r[0] == key]
        got.sort(key=lambda r: r[1], reverse=True)
        return [{"ts": dt.datetime.fromtimestamp(
                     ts, dt.timezone.utc).isoformat(),
                 "payload": p}
                for _k, ts, p in got[:int(limit)]]


@pytest.fixture
def hist(monkeypatch):
    fh = FakeHistory()
    monkeypatch.setattr(store, "save_history",
                        lambda key, payload: fh.save(key, payload))
    # indirect on purpose: a test may re-point `fh.fetch` (see the
    # unparseable-stamp case) and the reader must follow it.
    monkeypatch.setattr(store, "fetch_state_history",
                        lambda key, limit=800: fh.fetch(key, limit))
    return fh


# ---------------------------------------------------------------- the rollup

def test_a_publisher_built_census_accumulates_across_loops(hist):
    """THE HEADLINE: three loops of the same real census SUM. Before (vm) the
    third loop's payload simply replaced the second's and nothing added up."""
    cen = hull_census()
    assert cen["thin"] == 3 and cen["scanned"] == 5, cen   # the fixture's own premise
    for _ in range(3):
        assert store.snapshot_census("🧮 hull", cen) is True

    w = store.census_window("🧮 hull", hours=24)
    assert w["loops"] == 3
    assert w["thin"] == 9, w          # 3 refusals x 3 loops — SUMMED, not last
    assert w["scanned"] == 15, w
    assert w["below_band"] == 3 and w["eligible"] == 3, w


def test_the_stored_keys_are_the_publishers_own_keys(hist):
    """Rule 3, made executable: diff the stored row's keys against the dict the
    real publisher constructed. An invented key name here (`closed_at` vs
    `close_ts`, `ttl_sec` on a table with no such column) is this repo's single
    most repeated defect."""
    cen = hull_census()
    store.snapshot_census("🧮 hull", cen)
    stored = hist.rows[0][2]
    assert set(stored) - {store.CENSUS_DROPPED_KEY} == set(cen), \
        (sorted(set(stored)), sorted(set(cen)))


def test_the_key_is_the_bots_own_census_key(hist):
    store.snapshot_census("🧮 hull", hull_census())
    assert hist.rows[0][0] == "🧮 hull:census"


# ------------------------------------------------------- the fail-safe half

def test_empty_history_returns_empty_not_zeros(hist):
    """THE POINT OF THE WORK. {} means 'no data'; a zero-filled dict would read
    as 'measured, nothing refused' — the two must never be byte-identical."""
    w = store.census_window("never-published", hours=24)
    assert w == {}, w
    assert "loops" not in w and "slots_full" not in w


def test_every_sample_older_than_the_window_returns_empty_not_zeros(hist):
    """A book dark for three days is NO DATA in a 24h window, not a clean one."""
    old = time.time() - 72 * 3600.0
    hist.save("🧮 hull:census", {"thin": 3, "_dropped": 0}, at=old)
    assert store.census_window("🧮 hull", hours=24) == {}


def test_hours_is_the_actual_span_not_the_requested_one(hist):
    """A book that has published for 20 minutes must not claim a 24h rate."""
    now = time.time()
    for k in range(3):
        hist.save("🧮 hull:census", {"thin": 1, "_dropped": 0},
                  at=now - (40 - 20 * k) * 60.0)      # -40m, -20m, now
    w = store.census_window("🧮 hull", hours=24)
    assert w["loops"] == 3
    assert 0.65 < w["hours"] < 0.68, w["hours"]        # ~0.667h, NOT 24
    assert w["hours"] != 24


def test_a_single_sample_spans_zero_hours_rather_than_the_request(hist):
    """A rate is undefined on one loop; 24.0 would be a lie."""
    store.snapshot_census("🧮 hull", {"thin": 1})
    w = store.census_window("🧮 hull", hours=24)
    assert w["loops"] == 1 and w["hours"] == 0.0


# ------------------------------------------------------------ binding_gate

def test_binding_gate_names_a_refusal_and_never_a_denominator(hist):
    """`scanned` (15) outnumbers `thin` (9) in this window. A binding_gate that
    ranked raw counts would say 'scanned' and send the next session to widen
    the universe of a book whose real problem is its volume floor."""
    for _ in range(3):
        store.snapshot_census("🧮 hull", hull_census())
    w = store.census_window("🧮 hull", hours=24)
    assert w["binding_gate"] == "thin", w["binding_gate"]
    assert w["scanned"] > w["thin"]                    # the trap is live
    assert "scanned" in store.CENSUS_DENOMINATORS
    assert "eligible" in store.CENSUS_DENOMINATORS     # an OUTCOME never wins
    assert "held" in store.CENSUS_DENOMINATORS         # the book working, not starving


def test_binding_gate_is_none_when_nothing_was_refused(hist):
    store.snapshot_census("x", {"scanned": 9, "eligible": 9, "thin": 0})
    w = store.census_window("x", hours=24)
    assert w["binding_gate"] is None
    assert w["thin"] == 0                              # still reported, just not binding


def test_an_unclassifiable_key_is_summed_but_never_wins_binding_gate(hist):
    """A wrong guess is worse than no answer, so a key in neither declared set
    is EXCLUDED from binding_gate and named in `unclassified`. 🪁 kelly's
    `dev_p98_bps` is the live example: its SUM is meaningless."""
    for _ in range(2):
        store.snapshot_census("🪁 kelly", {"scanned": 4, "thin": 1,
                                           "dev_p98_bps": 900.0})
    w = store.census_window("🪁 kelly", hours=24)
    assert w["binding_gate"] == "thin"
    assert w["unclassified"] == ["dev_p98_bps"]
    assert w["dev_p98_bps"] == 1800.0                  # summed, and flagged
    # and the ranking itself is pinned: the gauge's sum (1800) DWARFS every
    # refusal here, so a binding_gate that ranked raw numbers would name it.
    assert w["dev_p98_bps"] > w["thin"] * 100


def test_binding_gate_is_none_when_nothing_is_classifiable(hist):
    """None-because-nothing-refused and None-because-nothing-readable are
    different facts; `unclassified` is what tells them apart."""
    store.snapshot_census("x", {"widget_frobs": 44})
    w = store.census_window("x", hours=24)
    assert w["binding_gate"] is None and w["unclassified"] == ["widget_frobs"]


def test_a_tie_is_deterministic(hist):
    store.snapshot_census("x", {"thin": 5, "capped": 5})
    a = store.census_window("x", hours=24)["binding_gate"]
    b = store.census_window("x", hours=24)["binding_gate"]
    assert a == b == "capped"                          # lexicographic tie-break


# --------------------------------------------------- flatten / drop / count

def test_one_nested_level_is_flattened_and_deeper_nests_are_dropped(hist):
    store.snapshot_census("🎯 sniper", {
        "watching": 212,
        "verdicts": {"no_signal": 22, "capped": 7},
        "sources": {"listing": {"scan": "dark"}},        # 2 deep -> dropped
    })
    w = store.census_window("🎯 sniper", hours=24)
    assert w["verdicts.no_signal"] == 22
    assert w["verdicts.capped"] == 7
    assert "sources.listing" not in w
    assert w["dropped"] == 1
    # the leaf is what classifies: `no_signal` is a declared refusal even
    # under a `verdicts.` parent, and it outranks `capped`.
    assert w["binding_gate"] == "verdicts.no_signal"


def test_a_string_verdict_is_dropped_and_counted(hist):
    """`scan: "fresh"` is a VERDICT. Storing it as junk, or float()-ing it into
    a fake measurement, are both worse than dropping it — but dropping it
    silently hides that the census is not fully countable."""
    store.snapshot_census("x", {"scan": "protections_locked", "thin": 2,
                                "coins": ["A", "B"]})
    w = store.census_window("x", hours=24)
    assert "scan" not in w and "coins" not in w
    assert w["thin"] == 2
    assert w["dropped"] == 2


def test_a_NUMERIC_string_is_still_dropped(hist):
    """The sharp half of the rule above, and my own first test round missed it:
    a `float()`-able string is still a VERDICT, not a count. Coercing "12"
    would turn a label into a measurement that no reader could tell from a
    real one — the one thing a counter must never do. Found by a mutation
    (float()-coerce every value) that my non-numeric fixtures let survive."""
    store.snapshot_census("x", {"scan": "12", "version": "3", "thin": 1})
    stored = hist.rows[0][2]
    assert "scan" not in stored and "version" not in stored, stored
    w = store.census_window("x", hours=24)
    assert w["dropped"] == 2 and w["thin"] == 1


def test_a_non_finite_float_never_reaches_storage(hist):
    """I5 — and it is dropped-and-counted, not stored as NaN."""
    store.snapshot_census("x", {"ratio": float("nan"), "gap": float("inf"),
                                "thin": 1})
    stored = hist.rows[0][2]
    assert "ratio" not in stored and "gap" not in stored
    assert stored[store.CENSUS_DROPPED_KEY] == 2
    assert store.census_window("x", hours=24)["dropped"] == 2


def test_a_bool_counts_as_one(hist):
    """🎯 the sniper publishes `capped: False`; summed over loops it answers
    'how many loops was this capped?' — which is the whole ask."""
    for v in (True, False, True):
        store.snapshot_census("🎯 sniper", {"offered": 1, "capped": v})
    w = store.census_window("🎯 sniper", hours=24)
    assert w["capped"] == 2 and w["loops"] == 3
    assert w["binding_gate"] == "capped"


def test_dropped_is_stamped_even_when_zero(hist):
    """I1 at field scale: an ABSENT `_dropped` means 'written before (vm)',
    never 'nothing was dropped'."""
    store.snapshot_census("x", {"thin": 1})
    assert hist.rows[0][2][store.CENSUS_DROPPED_KEY] == 0
    assert store.census_window("x", hours=24)["dropped"] == 0


def test_a_reserved_name_cannot_be_stored_and_is_counted(hist):
    """A census bucket called `hours` would be overwritten by the rollup's own
    field at read time — the (hj) second-copy failure wearing a dict key."""
    store.snapshot_census("x", {"hours": 99, "loops": 5, "thin": 3})
    stored = hist.rows[0][2]
    assert "hours" not in stored and "loops" not in stored
    assert stored[store.CENSUS_DROPPED_KEY] == 2
    w = store.census_window("x", hours=24)
    assert w["loops"] == 1 and w["hours"] == 0.0 and w["thin"] == 3


# ------------------------------------------------------------- housekeeping

def test_truncated_is_reported_when_the_fetch_hits_its_limit(hist):
    """A result exactly equal to its own limit is a truncation signature
    ((qz)); reporting it stops a SAMPLE reading as an exhaustive window."""
    for _ in range(5):
        store.snapshot_census("x", {"thin": 1})
    assert store.census_window("x", hours=24, limit=5)["truncated"] is True
    assert store.census_window("x", hours=24, limit=50)["truncated"] is False


def test_a_sample_with_an_unparseable_stamp_does_not_end_the_walk(hist):
    """Rows arrive newest-first, so a bad stamp that ENDED the walk would
    silently truncate the window to whatever preceded it."""
    real = hist.fetch

    def bent(key, limit=800):
        out = real(key, limit)
        if out:
            out[0] = dict(out[0], ts="not-a-timestamp")
        return out

    for _ in range(3):
        store.snapshot_census("x", {"thin": 1})
    hist.fetch = bent
    w = store.census_window("x", hours=24)
    assert w["loops"] == 2 and w["thin"] == 2       # the bad row alone is lost


def test_nothing_raises_on_junk(hist):
    """Telemetry never raises into a trading loop, and never returns a value
    that reads as a real measurement."""
    for junk in (None, [], 7, "census", {"a": {"b": {"c": 1}}}):
        store.snapshot_census("x", junk)
    for bad in (0, -1, "not-a-number", None, float("nan")):
        assert store.census_window("x", hours=bad) == {}


def test_a_dark_db_is_a_no_op(monkeypatch):
    """No seam injected: no DATABASE_URL under pytest, so the real
    save/fetch pair no-ops and the reader must NOT invent a window."""
    assert store.snapshot_census("x", {"thin": 1}) is False
    assert store.census_window("x", hours=24) == {}


def test_it_is_publish_only(hist):
    """PUBLISH-ONLY means publish-only: no gate, no lever, no clip in the
    module's census surface. Pinned so a later session cannot grow a consumer
    into a gate without this reddening."""
    import inspect
    src = "".join(inspect.getsource(f) for f in
                  (store.snapshot_census, store.census_window,
                   store._binding_gate, store._census_number))
    for forbidden in ("get_lever", "write_levers", "market_open", "publish("):
        assert forbidden not in src, forbidden
