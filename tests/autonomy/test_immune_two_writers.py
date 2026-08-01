"""A compromised LEDGER is the purest alive-but-sick shape in the fleet.

[2026-07-30 (hh)] `(hf)` measured that `perps-funding-carry-lshadow` is written
by TWO processes — 7 same-pair overlapping holds, deepest 9.14h on HYPE, and one
carry process cannot hold two positions in one coin because it keys `positions`
by coin and enters only `if c not in positions`. The row is fresh, in-TTL and
trusted; its `n` is two books' trades and `t` scales with sqrt(n).

`(hf)` gave the go-live gate a precondition and the dashboard a chip. Neither
reaches the operator, and **the fix is an operator action** — stop the duplicate
Railway service. A guard cannot un-pool closes two processes already wrote, so
the only useful response is to tell a human, once, until it stops. That is
precisely what `fleet_immune` is for: it covers the failure class the
death-oriented watchdog misses (alive but WRONG) and it phone-pushes NEW
sickness.

WHAT THESE TESTS PIN:
 1. The detector fires on a compromised book and is SILENT on a clean one in the
    same payload — a scanner that flags everything trains the operator to ignore
    it, which is worse than no scanner.
 2. `golive-readiness` is in the organ's FETCH list. Without that key the scanner
    is dead code — the registered-but-inert shape this repo keeps hitting, and
    the reason the key and the scanner must land in one commit.
 3. It reads the PUBLISHER's verdict rather than re-deriving overlaps, so the
    gate and the immune organ can never disagree about which ledgers are
    compromised.
 4. Stale is not sick (the watchdog's job), and a payload predating the
    integrity field does not crash the scan.
"""
import pathlib
import sys

import pytest

pytestmark = pytest.mark.autonomy

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "scripts"))

import fleet_immune as fi          # noqa: E402

NOW = 1_800_000_000.0
FRESH = fi._iso(NOW)


def _payload(books):
    return {"golive-readiness": {"updated": FRESH, "ttl_sec": 86400,
                                 "books": books}}


def _dup(**kw):
    d = {"two_writers": True, "same_pair_overlaps": 7, "deepest_overlap_h": 9.14,
         "deepest_overlap_pair": "HYPE", "peak_concurrent": 10}
    d.update(kw)
    return {"n": 82, "integrity": d}


CLEAN = {"n": 40, "integrity": {"two_writers": False, "same_pair_overlaps": 0,
                                "deepest_overlap_h": 0.0,
                                "deepest_overlap_pair": None,
                                "peak_concurrent": 4}}


# --------------------------------------------------------------------------
# 1. It fires, and only on the compromised book.
# --------------------------------------------------------------------------

def test_a_two_writer_ledger_is_flagged_as_sickness():
    out = fi.organ_invariants(_payload({"dup": _dup()}), NOW)
    assert len(out) == 1, out
    assert out[0]["organ"] == "golive-readiness"
    d = out[0]["detail"]
    assert "dup" in d and "TWO WRITERS" in d
    assert "9.14h on HYPE" in d, "the finding must carry its own measurement"
    assert "OPERATOR" in d, (
        "the fix is an operator action — a finding that does not say so reads as "
        "something the fleet will handle itself")


def test_a_clean_book_in_the_SAME_payload_stays_silent():
    """A detector that flags the whole payload is a detector the operator learns
    to ignore. Both books in one call, one finding out."""
    out = fi.organ_invariants(_payload({"dup": _dup(), "clean": CLEAN}), NOW)
    assert len(out) == 1 and "dup" in out[0]["detail"], out


def test_two_compromised_books_are_two_findings():
    out = fi.organ_invariants(_payload({"a": _dup(), "b": _dup(), "c": CLEAN}), NOW)
    assert len(out) == 2, out
    assert {"a", "b"} == {d["detail"].split(":")[0] for d in out}


def test_an_all_clean_gate_payload_is_silent():
    assert fi.organ_invariants(_payload({"a": CLEAN, "b": CLEAN}), NOW) == []


# --------------------------------------------------------------------------
# 2. The key is fetched — otherwise the scanner is dead code.
# --------------------------------------------------------------------------

def test_the_gate_key_is_in_the_organs_fetch_list():
    """This is the whole failure mode: a scanner reading a key the organ never
    asks the DB for is inert, and looks identical to a healthy fleet."""
    src = (_ROOT / "fleet_immune.py").read_text()
    i = src.index("_keys = (")
    block = src[i:i + 900]
    assert '"golive-readiness"' in block, (
        "golive-readiness is scanned but not fetched — the scanner cannot fire")


def test_the_publisher_owns_the_verdict_not_the_immune_organ():
    """It must read `integrity.two_writers`, never recompute overlaps. Two
    implementations of one question is how the gate and the organ end up
    disagreeing about which ledgers are compromised."""
    src = (_ROOT / "fleet_immune.py").read_text()
    assert "two_writers" in src
    assert "def same_pair_overlaps" not in src, (
        "the immune organ re-derives the detector — it must consume the gate's "
        "published verdict, which is the single owner")


# --------------------------------------------------------------------------
# 3. Fail-safe behaviour.
# --------------------------------------------------------------------------

def test_a_stale_gate_payload_is_not_sickness():
    """Death is the watchdog's job. This organ exists for FRESH-but-wrong, and
    treating stale as sick would page on every deploy."""
    stale = {"golive-readiness": {"updated": "2020-01-01T00:00:00+00:00",
                                  "ttl_sec": 86400, "books": {"a": _dup()}}}
    assert fi.organ_invariants(stale, NOW) == []


@pytest.mark.parametrize("books", [
    {},                                   # no books yet
    {"a": {"n": 12}},                     # publisher predates the field
    {"a": {"n": 12, "integrity": None}},  # explicit null
    {"a": None},                          # junk row
    {"a": {"integrity": "yes"}},          # wrong type
])
def test_a_malformed_or_older_payload_does_not_crash_the_scan(books):
    """The immune organ runs every 10 minutes across the whole fleet; a
    TypeError here would take out every OTHER invariant in the same call."""
    assert fi.organ_invariants(_payload(books), NOW) == []


def test_an_absent_gate_key_is_not_sickness():
    """Fail-safe open: a dark grader means no claim about any ledger, not a
    fleet-wide alarm."""
    assert fi.organ_invariants({}, NOW) == []


# --------------------------------------------------------------------------
# 4. THE SEAM. Both halves passing separately is not the same as the join.
# --------------------------------------------------------------------------

def test_the_REAL_grader_payload_reaches_the_immune_organ(monkeypatch):
    """Every test above builds the payload by hand, so a rename on the PUBLISHER
    side (`integrity` -> `ledger`, `two_writers` -> `duplicate_writers`) would
    leave this whole file green while the organ went blind. This drives the real
    `golive_readiness.main(--publish)`, captures what it actually writes to
    bot_state, and feeds THAT to the scanner.

    Two producers, one contract, and nothing between them but a field name."""
    import bot_pnl_store as store
    import golive_readiness as gr

    # a ledger with one compromised book and one clean one, in the DB's own shape
    rows = []
    for i in range(30):          # clean: sequential, distinct pairs
        rows.append({"bot": "clean-book", "pair": f"C{i}", "profit_abs": 1.0,
                     "profit_ratio": 0.003,
                     "open_ts": f"2026-07-{1 + i % 28:02d}T00:00:00+00:00",
                     "close_ts": f"2026-07-{1 + i % 28:02d}T06:00:00+00:00"})
    for i in range(12):          # compromised: two holds overlap on one pair
        rows.append({"bot": "dup-book", "pair": "HYPE", "profit_abs": 1.0,
                     "profit_ratio": 0.003,
                     "open_ts": f"2026-07-{10 + i:02d}T00:00:00+00:00",
                     "close_ts": f"2026-07-{12 + i:02d}T00:00:00+00:00"})

    saved = {}
    monkeypatch.setattr(store, "fetch_paper_trades", lambda limit=2000: rows)
    monkeypatch.setattr(store, "save_state",
                        lambda k, v: saved.setdefault(k, v) is None or True)
    monkeypatch.setattr(store, "save_history", lambda k, v: True)
    monkeypatch.setattr(sys, "argv", ["golive_readiness.py", "--min-closes",
                                      "10", "--publish"])
    import io
    import contextlib
    with contextlib.redirect_stdout(io.StringIO()):
        gr.main()

    payload = saved.get("golive-readiness")
    assert payload, "the grader published nothing — the seam has no left half"
    assert "dup-book" in payload["books"], payload["books"].keys()

    # [(ih)] The organ now pages only on a RECENT overlap, so this seam test
    # has to run its clock near the FIXTURE's own dates rather than at the
    # module-level NOW (which sits ~6 months after them). Deriving the clock
    # from the data keeps the test measuring the SEAM — that the grader's field
    # names reach the organ — instead of accidentally measuring the recency
    # window, which has its own tests below.
    import datetime as _d
    _fix_now = _d.datetime(2026, 7, 21, 2, 0, tzinfo=_d.timezone.utc).timestamp()
    payload["updated"] = fi._iso(_fix_now)     # freshness is the organ's gate
    assert payload["books"]["dup-book"]["integrity"].get("latest_overlap"), (
        "the grader must publish `latest_overlap` — without it the organ "
        "cannot tell an ongoing duplicate from a closed one (ih)")
    out = fi.organ_invariants({"golive-readiness": payload}, _fix_now)
    names = [o["detail"].split(":")[0] for o in out]
    assert names == ["dup-book"], (
        f"the organ read {names} off the grader's OWN payload — expected exactly "
        "the compromised book. A field rename on either side lands here.")
    assert "TWO WRITERS" in out[0]["detail"]


# ---------------------------------------------------------------------------
# (ih) 01-Aug — PAGE ONLY WHILE IT IS STILL HAPPENING.
#
# `two_writers` reads a PERMANENT ledger, so it is a one-way latch: once true
# it can never go false. That branch therefore paged every cycle with
# "OPERATOR: stop the duplicate Railway service" long after (hp)/(ic)/(id)
# closed the hole in code — an instruction with no object left, and one that
# (id) showed is now WRONG (the stood-down container is failover, not a fault).
#
# MEASURED on 🌾 carry: 7 overlaps, all between 17-Jul and 29-Jul 07:39Z,
# against a guard that merged 31-Jul 00:52Z. Zero since. A permanent page for
# a fixed condition is how a pager gets ignored ((hw): "a sticky error pages
# once and then means nothing").
#
# The FINDING is unchanged and still blocks READY upstream — only the PAGER is
# scoped, and only on positive evidence of recency.
# ---------------------------------------------------------------------------
def _iso_hours_ago(h):
    return fi._iso(NOW - h * 3600.0)


def test_a_historical_overlap_no_longer_pages():
    out = fi.organ_invariants(
        _payload({"dup": _dup(latest_overlap=_iso_hours_ago(72))}), NOW)
    assert out == [], (
        "a 3-day-old overlap still pages — the pager would fire forever on a "
        f"condition the code already closed: {out}")


def test_an_ONGOING_overlap_still_pages():
    out = fi.organ_invariants(
        _payload({"dup": _dup(latest_overlap=_iso_hours_ago(1))}), NOW)
    assert len(out) == 1, out
    d = out[0]["detail"]
    assert "TWO WRITERS" in d and "1.0h ago" in d, d
    assert "claim_writer" in d, (
        "the page must name what the operator can check NOW, not the retired "
        f"'stop the duplicate service' instruction (I8): {d}")


def test_an_unreadable_or_missing_stamp_stays_LOUD():
    """Fail-safe LOUD. A detector that mutes itself because it cannot tell is
    the failure it exists to prevent; absence is not evidence of recency."""
    for bad in (None, "", "not-a-date", 12345, {}):
        out = fi.organ_invariants(_payload({"dup": _dup(latest_overlap=bad)}), NOW)
        assert len(out) == 1, f"{bad!r} went quiet: {out}"
        assert "UNKNOWN time" in out[0]["detail"], out[0]["detail"]
    # and a payload with NO latest_overlap key at all (an older publisher)
    d = _dup()
    d["integrity"].pop("latest_overlap", None)
    out = fi.organ_invariants(_payload({"dup": d}), NOW)
    assert len(out) == 1 and "UNKNOWN time" in out[0]["detail"], out


def test_the_boundary_is_the_declared_constant():
    """Pinned so the window cannot be widened into uselessness without the
    test moving too — the (hz) lesson that the easiest way to 'fix' a finding
    is to stop measuring it."""
    assert 1.0 <= fi.DUP_WRITER_CLOSED_H <= 48.0, fi.DUP_WRITER_CLOSED_H
    just_inside = fi.organ_invariants(
        _payload({"dup": _dup(latest_overlap=_iso_hours_ago(fi.DUP_WRITER_CLOSED_H - 0.5))}), NOW)
    just_outside = fi.organ_invariants(
        _payload({"dup": _dup(latest_overlap=_iso_hours_ago(fi.DUP_WRITER_CLOSED_H + 0.5))}), NOW)
    assert len(just_inside) == 1 and just_outside == [], (just_inside, just_outside)
