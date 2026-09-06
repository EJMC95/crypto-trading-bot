"""The replay harness must normalise the ledger with the brain's OWN owner.

[2026-09-07 (yi)] `brain_replay.load_trades` carried a PARTIAL hand-written
copy of `bot_pnl_store.fetch_paper_trades`' normalisation whose own docstring
claimed it normalised "exactly like" it. It did not, in two ways that both
reach the verdict:

  1. IT IGNORED THE `tag` COLUMN. Production prefers a stored tag over the
     reason prefix ("'long-funding' beats 'long'"); the harness derived the
     bucket key from `split_reason(reason)` alone. Measured on the live feed:
     366 of 4,288 rows bucket differently, and BOTH Funding Farmer arms
     partition at a granularity production never uses — the shadow arm reads
     {short 188, long 17} in the harness against {short-funding 162,
     long-funding 16, short 26, long 1} in production, era-filtered.
  2. IT NEVER APPLIED THE LEDGER QUARANTINE. 47 rows the production brain
     withholds as real-trades-but-not-evidence reached the harness.

So the instrument that VALIDATES the brain graded its engines on a universe
the brain does not have. Measured the day it was fixed, every headline the
harness prints moves — v3 half-1 goes -0.815 -> +0.068, a SIGN CHANGE in one
of the two halves the go-live bar reads.

AND IT WAS CI-INVISIBLE. `brain_replay` is registered in
tests/test_selftests.py, but its `selftest()` is documented "OFFLINE
validation — no ledger fetch" and exercises only the synthetic suite;
`load_trades()` is reachable ONLY from `main()`. No fixture in the tree drove
this normaliser, which is why a partial copy survived in it. These tests are
that fixture.

The fix is the doctrine's, not a patch of the copy: a second copy of a rule
is a second rule ((hj)), so the normalisation has ONE owner —
`bot_pnl_store.normalize_paper_row` — and both transports call it.
"""
import ast
import inspect

import pytest

import bot_pnl_store
import brain_replay

pytestmark = pytest.mark.autonomy


# --------------------------------------------------------------------------
# 1. ONE owner — pinned by identity and by AST, not by a substring.
# --------------------------------------------------------------------------

def _load_trades_ast():
    tree = ast.parse(inspect.getsource(brain_replay.load_trades))
    return next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "load_trades")


def test_the_harness_calls_the_production_owner():
    """Pin the call site itself. A substring check would pass against a
    docstring that merely NAMES the owner while a copy runs underneath."""
    node = _load_trades_ast()
    called = {n.func.id for n in ast.walk(node)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "normalize_paper_row" in called, (
        "load_trades must normalise through bot_pnl_store.normalize_paper_row; "
        f"it calls {sorted(called)}")


def test_the_owner_the_harness_imports_is_the_one_production_uses():
    """Identity, per (hj): re-use is pinned by `is`, never by name."""
    imported = {a.name for n in ast.walk(_load_trades_ast())
                if isinstance(n, ast.ImportFrom) and n.module == "bot_pnl_store"
                for a in n.names}
    assert "normalize_paper_row" in imported
    src = inspect.getsource(bot_pnl_store.fetch_paper_trades)
    assert "normalize_paper_row(" in src, (
        "production must call the same owner, or the harness is validating "
        "the brain against a rule the brain does not run")


def test_the_harness_does_not_re_derive_the_bucket_key():
    """The exact defect: a local `split_reason(...)` in load_trades IS the
    second copy, whatever else the function also calls."""
    node = _load_trades_ast()
    local = [n for n in ast.walk(node)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == "split_reason"]
    assert not local, (
        "load_trades re-derives the bucket key locally — that is the copy "
        "this test exists to forbid; the owner already does it, tag-first")


# --------------------------------------------------------------------------
# 2. The two behaviours the copy got wrong, driven end-to-end.
# --------------------------------------------------------------------------

def _publisher_keys():
    """The KEY NAMES come from the publisher's own SELECT, parsed out of
    `pnl_dashboard.fetch_paper_rows` — never hand-typed. A fixture that
    invents its keys cannot catch the publisher dropping one."""
    import pnl_dashboard
    src = inspect.getsource(pnl_dashboard.fetch_paper_rows)
    sel = src[src.index('"SELECT bot,'):]
    sel = sel[: sel.index("FROM paper_trades")]
    cols = "".join(ln.strip().strip('"f ') for ln in sel.splitlines())
    return [c.strip() for c in cols.replace("SELECT", "").split(",") if c.strip()]


def test_the_feed_still_serves_every_column_the_owner_needs():
    """If the dashboard's SELECT ever drops `tag`, the harness silently goes
    back to reason-prefix bucketing. That must redden a push, not a verdict."""
    keys = _publisher_keys()
    for needed in ("bot", "pair", "pnl_abs", "pnl_pct", "opened_at",
                   "closed_at", "reason", "tag", "side"):
        assert needed in keys, (
            f"pnl_dashboard.fetch_paper_rows no longer serves {needed!r}: "
            f"{keys}")
    # the ONE declared divergence — asserted so it stays declared, not drifted
    assert "venue" not in keys, (
        "the feed now serves `venue`; the divergence declared in "
        "normalize_paper_row's docstring is stale — pass it and delete the note")


def _drive(rows, monkeypatch):
    """Run the real load_trades over a fixture built on publisher key names."""
    keys = _publisher_keys()
    payload = []
    for r in rows:
        assert set(r) <= set(keys), f"fixture invents keys: {set(r) - set(keys)}"
        payload.append({k: r.get(k) for k in keys})
    monkeypatch.setattr(brain_replay, "fetch",
                        lambda url: payload if "source=paper" in url else [])
    return brain_replay.load_trades()


OPEN, CLOSE = "2026-08-01T00:00:00Z", "2026-08-01T04:00:00Z"


def test_a_stored_tag_beats_the_reason_prefix(monkeypatch):
    """Defect 1, on the shape that actually moved: the Farmer stamps
    tag='short-funding' while its reason prefix is a bare 'short'."""
    got = _drive([{"bot": "perps-funding-lighter-lshadow", "pair": "BTC",
                   "pnl_abs": 1.0, "pnl_pct": 0.01, "opened_at": OPEN,
                   "closed_at": CLOSE, "reason": "short_decay_paid",
                   "tag": "short-funding"}], monkeypatch)
    assert len(got) == 1
    assert got[0]["enter_tag"] == "short-funding", (
        "the stored tag was ignored — the harness is bucketing on the reason "
        "prefix again, which is the partition production never uses")
    assert got[0]["exit_reason"] == "decay_paid"


def test_the_reason_prefix_stays_the_fallback_for_untagged_rows(monkeypatch):
    """Tag-preference must not become tag-REQUIREMENT: pre-stamp rows still
    bucket off the reason, exactly as production does."""
    for tag in (None, ""):
        got = _drive([{"bot": "b", "pair": "BTC", "pnl_abs": 1.0,
                       "pnl_pct": 0.01, "opened_at": OPEN, "closed_at": CLOSE,
                       "reason": "long_decay_paid", "tag": tag}], monkeypatch)
        assert got and got[0]["enter_tag"] == "long", (tag, got)


def test_a_quarantined_row_never_reaches_the_replay(monkeypatch):
    """Defect 2, driven off the REAL quarantine table — so a row that is only
    quarantined because LEDGER_QUARANTINE says so is the one under test."""
    q_pair, q_bot, lo, _hi, _why = bot_pnl_store.LEDGER_QUARANTINE[0]
    rows = [
        {"bot": q_bot, "pair": q_pair, "pnl_abs": 5.0, "pnl_pct": 0.05,
         "opened_at": lo + "T00:00:00Z", "closed_at": lo + "T04:00:00Z",
         "reason": "long_tp", "tag": None},
        {"bot": "clean-book", "pair": "ETH", "pnl_abs": 1.0, "pnl_pct": 0.01,
         "opened_at": OPEN, "closed_at": CLOSE, "reason": "long_tp",
         "tag": None},
    ]
    got = _drive(rows, monkeypatch)
    assert [t["bot"] for t in got] == ["clean-book"], (
        "a LEDGER_QUARANTINE row reached the replay; the production brain "
        f"withholds it: {got}")


def test_a_skip_row_is_still_dropped(monkeypatch):
    """The transport's own filter. It is NOT in the shared owner (a query
    predicate is not row normalisation), so it needs its own pin here."""
    got = _drive([{"bot": "sniper", "pair": "X", "pnl_abs": 0.0,
                   "pnl_pct": 0.0, "opened_at": OPEN, "closed_at": CLOSE,
                   "reason": "long_gate", "side": "skip", "tag": None}],
                 monkeypatch)
    assert got == [], f"a side='skip' gate log reached the replay: {got}"


# --------------------------------------------------------------------------
# 3. The owner itself — production reads this path with real money behind it.
# --------------------------------------------------------------------------

def test_the_owner_returns_none_only_for_a_quarantined_row():
    """None has exactly ONE meaning, so `fetch_paper_trades` can count
    withheld rows without mislabelling anything else as a quarantine."""
    q_pair, q_bot, lo, _hi, _why = bot_pnl_store.LEDGER_QUARANTINE[0]
    assert bot_pnl_store.normalize_paper_row(
        q_bot, q_pair, 1.0, 0.01, lo + "T00:00:00Z", lo + "T04:00:00Z",
        "long_tp") is None
    # junk in every other field must still yield a ROW, never a silent drop
    row = bot_pnl_store.normalize_paper_row(
        None, None, None, None, "junk", "junk", None, extra="notadict",
        entry_price="junk", exit_price=None, tag=0)
    assert row is not None and row["profit_abs"] == 0.0
    assert row["duration_min"] is None and row["open_rate"] is None
    assert row["extra"] == {}


def test_the_owner_keeps_an_absent_price_absent():
    """(hr)-adjacent: a missing fill price must read as ABSENT evidence, never
    as 0.0, which would look like a real price."""
    row = bot_pnl_store.normalize_paper_row(
        "b", "BTC", 1.0, 0.01, OPEN, CLOSE, "long_tp",
        entry_price=None, exit_price=None)
    assert row["open_rate"] is None and row["close_rate"] is None
    row = bot_pnl_store.normalize_paper_row(
        "b", "BTC", 1.0, 0.01, OPEN, CLOSE, "long_tp",
        entry_price=1.5, exit_price="2.5")
    assert row["open_rate"] == 1.5 and row["close_rate"] == 2.5


# --------------------------------------------------------------------------
# 4. The class, not the instance — the THIRD reader of this rule.
# --------------------------------------------------------------------------

def test_the_floors_study_still_agrees_with_the_owner_about_the_bucket_key():
    """`scripts/study_brain_floors_2026-09-02.py::enter_tag_of` carries its own
    spelling of the tag-beats-reason rule. It is DECLARED, not refactored: the
    study is a CALIBRATED instrument (3/3 against the live payload) and routing
    it through the owner would also apply the ledger quarantine, changing the
    sample its calibration gate was tuned on — a real risk for zero measured
    gain today, since the two agree everywhere.

    So this is a DRIFT ARM (the `audit_lever_bounds` shape): the copy may stay,
    it may not silently disagree. If it ever does, this fails and whoever
    changed one of them decides which is right.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_sbf", "scripts/study_brain_floors_2026-09-02.py")
    sbf = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sbf)

    for reason in ("long_decay_paid", "short_stop", "long", "", None, "weird"):
        for tag in (None, "", "long-funding", "short-navband_tp", "long",
                    "short", 0):
            row = bot_pnl_store.normalize_paper_row(
                "b", "BTC", 1.0, 0.01, OPEN, CLOSE, reason, tag=tag)
            assert row is not None
            theirs = sbf.enter_tag_of({"tag": tag, "reason": reason})
            assert (theirs or None) == row["enter_tag"], (
                f"the floors study and the owner disagree on the bucket key "
                f"for reason={reason!r} tag={tag!r}: {theirs!r} vs "
                f"{row['enter_tag']!r}")
