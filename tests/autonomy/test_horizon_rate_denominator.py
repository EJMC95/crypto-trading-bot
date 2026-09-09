"""The rate denominator must not include days the book could not trade.
[2026-09-09 (zi)]

THE DEFECT. `(la)` moved the horizon's rate denominator from `now - first_close`
to `now - min(first_close, era_start)`, on a correct argument: *"a book that
HOLDS necessarily takes one holding period to produce its first in-era close"*,
so measuring from the first close prices the wait out of existence (🌾 carry
holds 65-70h and would have read 2-3x its true throughput).

The quantity that argument needs is ONE HOLDING PERIOD. The era boundary was
used as a stand-in for it — and a stand-in is only as good as the gap between
the two.

IT MATTERED on REAL MONEY. Measured 9-Sep on the live payload, 🙏 avo's LIVE
arm: era `{since: 2026-07-17, source: declared}` — the family-wide accrual
date — but the row did not become the live arm until 13-Aug and its first close
was 22.3d old. Twenty-seven of the 54.2 denominator days were days on which the
arm held no capital and could not have closed anything. `rate_cpd` published
**0.33/day** where the row's own `progression` published **1.00/day** over 7
days, and the `closes` bar — the one that BINDS her — projected **2026-10-15**
against her own ~12 days.

THE FIX is the measured quantity rather than the stand-in: the FIRST IN-ERA
OPEN. By construction `era_start <= first_open <= first_close` (the era is
keyed on the open), so it sits BETWEEN the two options (la) weighed and keeps
(la)'s protection in full — the open→close wait is still inside the
denominator.

WHAT MUST NOT MOVE, and these tests pin it in both directions:
  * the TRAILING stall — last close → now — which is the stall the doctrine
    actually measured (dad's span-rate read 2.2x its age-rate after a 7-11d
    stall). The denominator still ends at `now`.
  * (la)'s holding-period protection: a HOLDING book must still not be graded
    from its first close.
  * the WINDOW floor, which is calendar and has nothing to do with throughput.
  * every fail-safe: a missing / junk / out-of-order open falls back to the
    pre-(zi) base EXACTLY.

And the credit granted is PUBLISHED (`rate_lead_in_days`), never absorbed, so a
book that is genuinely starving before its first in-era open shows the number
instead of hiding it.
"""
import datetime as dt
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import golive_readiness as g            # noqa: E402

NOW = dt.datetime(2026, 9, 9, tzinfo=dt.timezone.utc)


def _rows(n=20, first_close_days_ago=22.3, usd=20.0, pct=0.01):
    """`n` closes, oldest first, evenly spread from `first_close_days_ago`."""
    out = []
    for i in range(n):
        ts = NOW - dt.timedelta(
            days=first_close_days_ago * (1 - i / max(1, n - 1)))
        out.append((pct, pct * usd, ts))
    return out


def _hz(rows, era_days_ago=None, open_days_ago=None, **kw):
    era = (NOW - dt.timedelta(days=era_days_ago)).timestamp() \
        if era_days_ago is not None else None
    fo = NOW - dt.timedelta(days=open_days_ago) \
        if open_days_ago is not None else None
    return g.gate_horizon(g.stats(rows), first_close=rows[0][2],
                          era_epoch=era, now=NOW, first_open=fo, **kw)


# --------------------------------------------------------------- the defect
def test_the_rate_excludes_era_days_before_the_books_first_trade():
    """🙏 avo's live shape: era 54.2d old, first OPEN 25.0d (her ~3d hold
    ahead of a first close 22.3d old), 18 closes. The open is deliberately
    NOT within a rounding tolerance of the close, so a mutation that swaps
    the denominator for the first-close age cannot hide inside `approx`."""
    rows = _rows(n=18, first_close_days_ago=22.3)
    before = _hz(rows, era_days_ago=54.2)                 # pre-(zi) base
    after = _hz(rows, era_days_ago=54.2, open_days_ago=25.0)
    assert before["rate_cpd"] == pytest.approx(18 / 54.2, abs=0.01), before
    assert after["rate_cpd"] == pytest.approx(18 / 25.0, abs=0.01), after
    assert after["rate_cpd"] > before["rate_cpd"] * 2, (before, after)
    assert after["rate_basis"] == "first-open", after
    # and the 29.2 days of era lead-in are PUBLISHED, not absorbed
    assert after["rate_lead_in_days"] == pytest.approx(54.2 - 25.0, abs=0.05)


def test_the_denominator_is_published_so_a_reader_never_recomputes_it():
    """(zi)'s second half: the one number behind every date was invisible."""
    rows = _rows(n=18, first_close_days_ago=22.3)
    hz = _hz(rows, era_days_ago=54.2, open_days_ago=25.0)
    assert hz["rate_basis_days"] == pytest.approx(25.0, abs=0.1), hz
    assert hz["rate_since"] == (NOW - dt.timedelta(days=25.0)).date().isoformat()
    # the published pieces must reproduce the published rate
    assert hz["rate_cpd"] == pytest.approx(18 / hz["rate_basis_days"], abs=0.01)


def test_every_early_return_path_carries_the_basis_keys():
    """The I6 rule the defaults block already states: a consumer must never
    infer the basis from a key's absence."""
    keys = ("rate_basis", "rate_since", "rate_basis_days", "rate_lead_in_days")
    for hz in (g.gate_horizon({}, now=NOW),                       # junk stats
               g.gate_horizon(g.stats(_rows(n=2)),                # n < n_rate
                              first_close=_rows(n=2)[0][2], now=NOW),
               _hz(_rows(n=40, pct=0.02), era_days_ago=54.2,      # ready
                   open_days_ago=45.0)):
        for k in keys:
            assert k in hz, (k, hz)


# ------------------------------------------------- what must NOT move (I3)
def test_la_is_preserved_a_holding_book_is_not_graded_from_its_first_close():
    """🌾 carry: era 40d, first OPEN 3d before the first close (a 65-70h hold).
    The wait must stay INSIDE the denominator — that is (la)'s whole point."""
    # n=25 keeps the `closes` bar failing, so the sample still gets a
    # projection: a six-of-six fixture returns `ready` before the rate block
    # and would pin nothing (it silently did, in this file's first draft).
    rows = _rows(n=25, first_close_days_ago=35.4)
    hz = _hz(rows, era_days_ago=40.0, open_days_ago=35.4 + 2.9)
    assert hz["rate_basis"] == "first-open", hz
    # from the first OPEN (38.3d), never the first CLOSE (35.4d)
    assert hz["rate_cpd"] == pytest.approx(25 / 38.3, abs=0.01), hz
    naive_from_close = 25 / 35.4
    assert hz["rate_cpd"] < naive_from_close, (
        "the open→close hold has fallen out of the denominator — this is "
        "exactly the overstatement (la) shipped to prevent")


def test_a_trailing_stall_still_dilutes_the_rate():
    """The stall the doctrine MEASURED is last-close → now, and it is untouched:
    the denominator ends at `now` whatever the base is."""
    quiet = _rows(n=20, first_close_days_ago=30.0)
    # same 20 closes, same first open — but they all finished 20 days ago
    stalled = [(p, u, ts - dt.timedelta(days=20)) for p, u, ts in quiet]
    hz_q = _hz(quiet, era_days_ago=40.0, open_days_ago=30.1)
    hz_s = g.gate_horizon(g.stats(stalled), first_close=stalled[0][2],
                          era_epoch=(NOW - dt.timedelta(days=60)).timestamp(),
                          now=NOW,
                          first_open=NOW - dt.timedelta(days=50.1))
    assert hz_s["rate_cpd"] < hz_q["rate_cpd"], (hz_q, hz_s)
    assert hz_s["rate_basis_days"] > hz_q["rate_basis_days"] + 15


def test_the_window_floor_is_calendar_and_does_not_move():
    """The window bar is pure calendar — 👩 mum LIVE's ETA is immune, which is
    why the defect bit exactly one book. Same n<HORIZON_MIN_N_RATE floor."""
    rows = _rows(n=2, first_close_days_ago=10.0)
    a = g.gate_horizon(g.stats(rows), first_close=rows[0][2],
                       era_epoch=(NOW - dt.timedelta(days=50)).timestamp(),
                       now=NOW)
    b = g.gate_horizon(g.stats(rows), first_close=rows[0][2],
                       era_epoch=(NOW - dt.timedelta(days=50)).timestamp(),
                       now=NOW, first_open=NOW - dt.timedelta(days=10.1))
    assert a["eta"] == b["eta"], (a, b)


def test_a_book_with_no_declared_era_still_measures_from_its_first_open():
    """Six living books carry no declared era. Before this branch existed they
    fell through to the first CLOSE — the exact (la) overstatement, one class
    over — because the floor test compared against a base that WAS the close.
    With no era the open is simply where the book's life began; the hold joins
    the denominator, and there is no era credit to publish."""
    rows = _rows(n=20, first_close_days_ago=22.3)
    hz = _hz(rows, era_days_ago=None, open_days_ago=25.0)
    assert hz["rate_basis"] == "first-open", hz
    assert hz["rate_cpd"] == pytest.approx(20 / 25.0, abs=0.01), hz
    assert hz["rate_lead_in_days"] is None, "no era ⇒ nothing was credited"
    # and the fail-safe still refuses an open after the close, era or not
    bad = g.gate_horizon(g.stats(rows), first_close=rows[0][2], now=NOW,
                         first_open=NOW - dt.timedelta(days=1))
    assert bad["rate_basis"] == "first-close", bad
    assert bad["rate_cpd"] == pytest.approx(20 / 22.3, abs=0.01), bad


# ------------------------------------------------------------- fail-safes
@pytest.mark.parametrize("bad, why", [
    (None, "absent"),
    ("not-a-datetime", "junk type"),
    (NOW + dt.timedelta(days=1), "in the future, after the first close"),
    (NOW - dt.timedelta(days=1), "AFTER the first close"),
    (NOW - dt.timedelta(days=99), "BEFORE the era boundary"),
])
def test_a_malformed_open_falls_back_to_the_pre_zi_base_exactly(bad, why):
    rows = _rows(n=18, first_close_days_ago=22.3)
    base = _hz(rows, era_days_ago=54.2)
    got = _hz(rows, era_days_ago=54.2)
    got = g.gate_horizon(g.stats(rows), first_close=rows[0][2],
                         era_epoch=(NOW - dt.timedelta(days=54.2)).timestamp(),
                         now=NOW, first_open=bad)
    assert got["rate_cpd"] == base["rate_cpd"], (why, got, base)
    assert got["rate_basis"] == "era", (why, got)
    assert got["rate_lead_in_days"] is None, (why, got)


def test_a_naive_open_is_read_as_utc_not_as_local():
    """A tz-naive stamp must not silently shift the denominator by the host's
    offset — every instant in this fleet is UTC."""
    rows = _rows(n=18, first_close_days_ago=22.3)
    aware = _hz(rows, era_days_ago=54.2, open_days_ago=25.0)
    naive = g.gate_horizon(
        g.stats(rows), first_close=rows[0][2],
        era_epoch=(NOW - dt.timedelta(days=54.2)).timestamp(), now=NOW,
        first_open=(NOW - dt.timedelta(days=25.0)).replace(tzinfo=None))
    assert naive["rate_cpd"] == aware["rate_cpd"], (naive, aware)


# ------------------------------------------------ the owner of the quantity
def test_first_era_open_is_a_min_not_the_first_row():
    """Rows are ordered by CLOSE. A book that holds can close a later-opened
    trade first — every basket book does — so `rows[0][3]` is wrong and a
    min() over the column is right."""
    t = NOW - dt.timedelta(days=10)
    rows = [                                   # ordered by close, oldest first
        (0.01, 0.2, t, (t - dt.timedelta(days=1)).isoformat()),
        (0.01, 0.2, t + dt.timedelta(hours=1),
         (t - dt.timedelta(days=9)).isoformat()),      # opened EARLIEST
    ]
    got = g.first_era_open(rows)
    assert got == t - dt.timedelta(days=9), got
    assert got != g._era_parse()(rows[0][3]), "took rows[0], not the min"


def test_first_era_open_skips_an_unreadable_stamp_and_never_returns_epoch_zero():
    """Coercing an unreadable open to 0.0 would hand the rate a 56-year
    denominator and read every book as dead."""
    t = NOW - dt.timedelta(days=10)
    good = (t - dt.timedelta(days=1)).isoformat()
    rows = [(0.01, 0.2, t, "not-a-timestamp"),
            (0.01, 0.2, t, None),
            (0.01, 0.2, t),                     # short row, no open column
            (0.01, 0.2, t, good)]
    got = g.first_era_open(rows)
    assert got == dt.datetime.fromisoformat(good), got
    assert got.year > 2000, got
    assert g.first_era_open([]) is None
    assert g.first_era_open([(0.01, 0.2, t, "junk")]) is None


def test_the_call_sites_read_the_owner_and_never_index_the_open_column():
    """(hj): a second copy of a rule is a second rule. Both `gate_horizon`
    call sites in the publish path must go through `first_era_open`."""
    import ast
    src = (ROOT / "scripts" / "golive_readiness.py").read_text()
    tree = ast.parse(src)
    # The publish path is the set of calls that hand the horizon the era
    # `era_rows` resolved (`era_epoch=_era_ep`); the selftest's own calls pass
    # literals and are not it. Renaming that variable fails this loudly, which
    # is the right outcome — re-aim the pin deliberately, never silently.
    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Name) and n.func.id == "gate_horizon"
             and any(k.arg == "era_epoch" and isinstance(k.value, ast.Name)
                     and k.value.id == "_era_ep" for k in n.keywords)]
    assert len(calls) == 2, f"expected both publish-path call sites, got {len(calls)}"
    for c in calls:
        fo = [k for k in c.keywords if k.arg == "first_open"]
        assert fo, "a publish-path gate_horizon call passes no first_open"
        assert isinstance(fo[0].value, ast.Call) and \
            isinstance(fo[0].value.func, ast.Name) and \
            fo[0].value.func.id == "first_era_open", \
            "first_open is being derived inline instead of from the owner"
