"""[2026-08-27 (vm)] 👩 mum's entry cell is a CONJUNCTION, and only one half
of it was ever gauged.

Her rule is `rsi < RSI_MAX and NOT uptrend and v > 0`. `(rr)` built the RSI
gauge (`rsi_bar` / `rsi_min` / `near_bar`) and the trend term got nothing —
and `census_no_entry_why` reports `uptrend_blocked` ONLY once RSI has ALSO
passed, so whenever RSI is the tighter term the NOT-uptrend conjunct counts
exactly zero. Measured on her live row 27-Aug, after `(ve)` moved the bar to
36.0:

    scan {universe: 23, rsi_bar: 36.0, rsi_min: 27.8, near_bar: 5,
          verdicts: {no_signal: 22, uptrend_blocked: 1}}

The RSI half is MET (27.8 < 36.0) — her binding gate had MOVED to the trend
term and not one field on the row said so, on a book that has taken ZERO
trades since going live 25-Aug. So `MUM_RSI_MAX` could not be priced either
way: nobody could say how many of those 5 near-bar coins are even outside an
uptrend.

WHAT IS PINNED HERE, in the order it matters:
  1. `outside_uptrend_n` counts the trend term INDEPENDENT of RSI — the
     defect cell is a coin outside an uptrend whose RSI is above the bar,
     which the verdict map buckets `no_signal` and this must still count;
  2. `both_terms_n` is the SHIPPED rule's own `enter`, driven through
     `OversoldRebound.signals` rather than a re-typed copy of the condition
     ((hj): a second copy of a rule is a second rule, and a census that
     disagrees with the gate is worse than no census);
  3. the fail-safe half — absent rather than zero on no readings, and a
     non-bool `uptrend` never read as "outside" (I8: a fabricated PASS is the
     loudest possible reading from no data);
  4. the loop actually FEEDS both maps (a gauge nothing writes to is the
     registered-but-inert shape, I18) — asserted on the AST, because a
     substring is not a wiring test;
  5. `census_24h` — the scan census accumulated over a day through
     `bot_pnl_store`'s own owner, so a refusal finally has a denominator;
  6. blast radius: no other family book's payload shape moves, and nothing
     here is read by a gate.

THE SEAM for (5) is the same one `test_census_accumulation.py` uses — the
`save_history` / `fetch_state_history` module globals, the two functions
`snapshot_census` / `census_window` call by name. Nothing here mocks either
of those two, and the census payloads are PUBLISHER-BUILT: they come out of
`_census_extra` fed by `OversoldRebound.signals` over real bar arrays.
"""
import ast
import pathlib
import sys
import time

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import bot_pnl_store as store    # noqa: E402
import lighter_family_bot as fam  # noqa: E402


def _mum():
    for s in fam.STRATEGIES:
        if s.bot == "freqtrade-mum":
            return s
    raise AssertionError("freqtrade-mum is not in STRATEGIES at all")


def _bars(closes):
    return {"c": closes, "h": [x * 1.004 for x in closes],
            "l": [x * 0.996 for x in closes], "v": [10.0] * len(closes),
            "t": list(range(len(closes)))}


N = 300


def _tape(kind):
    """Four REAL tapes covering every cell of mum's 2x2 entry cell. Verified
    against the shipped `signals()` by `test_the_fixture_covers_all_four_cells`
    below — a fixture whose premise is not asserted is a fixture that rots."""
    if kind == "down":            # outside uptrend, rsi 0.0  -> ENTER
        return [100.0 - 0.2 * i for i in range(N)]
    if kind == "down_rally":      # outside uptrend, rsi 95.6 -> the DEFECT cell
        base = [100.0 - 0.2 * i for i in range(N - 12)]
        return base + [base[-1] + 3.0 * (k + 1) for k in range(12)]
    if kind == "up_dip":          # uptrend, rsi 6.5 -> `uptrend_blocked`
        base = [50.0 + 0.2 * i for i in range(N - 12)]
        return base + [base[-1] - 2.0 * (k + 1) for k in range(12)]
    return [50.0 + 0.2 * i for i in range(N)]     # uptrend, rsi 100 -> nothing


class _B:
    """The three attributes `_census_extra` reads off a Book, nothing else."""

    def __init__(self, strat):
        self.s = strat
        self.bot_id = strat.bot + "-lshadow"
        self.scan = {"scanned": 0, "opened": 0}
        self.last_rsi = {}
        self.last_uptrend = {}
        self.last_enter = {}
        self._rollup = None
        self._rollup_at = 0.0


def _drive(kinds, strat=None):
    """Run the SHIPPED `signals()` over each tape and capture exactly what the
    scan loop captures. This is the publisher-built path: no sig dict in this
    file is hand-written."""
    b = _B(strat or _mum())
    for i, kind in enumerate(kinds):
        sig = b.s.signals(_bars(_tape(kind)), {})
        coin = f"C{i}"
        b.scan["scanned"] += 1
        if sig and isinstance(sig.get("rsi"), (int, float)):
            b.last_rsi[coin] = float(sig["rsi"])
        if sig and isinstance(sig.get("uptrend"), bool):
            b.last_uptrend[coin] = sig["uptrend"]
        if sig:
            b.last_enter[coin] = bool(sig.get("enter"))
    return b


# --- 0 · the fixture's own premise ----------------------------------------

def test_the_fixture_covers_all_four_cells():
    """rsi x uptrend, all four corners, off the shipped rule. If a future
    parameter move collapses two cells into one this fails HERE rather than
    quietly making the tests below vacuous — the `(po)` lesson: a check that
    inspects nothing reports clean."""
    s = _mum()
    got = {}
    for kind in ("down", "down_rally", "up_dip", "up"):
        sig = s.signals(_bars(_tape(kind)), {})
        assert sig is not None, kind
        got[kind] = (sig["rsi"] < s.RSI_MAX, sig["uptrend"], bool(sig["enter"]))
    assert got["down"] == (True, False, True), got
    assert got["down_rally"] == (False, False, False), got   # the defect cell
    assert got["up_dip"] == (True, True, False), got
    assert got["up"] == (False, True, False), got


# --- 1 · the trend term, independent of RSI -------------------------------

def test_the_trend_term_counts_when_rsi_is_the_TIGHTER_one():
    """THE DEFECT. `down_rally` is outside an uptrend and its RSI is above the
    bar, so the verdict map calls it `no_signal` and `uptrend_blocked` stays 0.
    Before (vm) that coin was invisible: the row could not say the trend half
    of the cell was passing on it."""
    b = _drive(["down_rally", "up", "up"])
    scan = fam._census_extra(b)["scan"]
    assert fam.census_no_entry_why(b.s, b.s.signals(
        _bars(_tape("down_rally")), {})) == "no_signal", \
        "premise: the verdict map cannot see this coin's trend term"
    assert scan["outside_uptrend_n"] == 1, scan
    assert scan["both_terms_n"] == 0, scan


def test_outside_uptrend_counts_every_coin_outside_regardless_of_rsi():
    b = _drive(["down", "down_rally", "up_dip", "up"])
    scan = fam._census_extra(b)["scan"]
    # down + down_rally are outside; up_dip + up are inside
    assert scan["outside_uptrend_n"] == 2, scan
    # ...and it is NOT the near-bar count wearing a new name: near_bar is
    # rsi-only and picks the other pair (0.0 and 6.5, both within bar+8).
    assert scan["near_bar"] == 2 and scan["rsi_read"] == 4, scan
    assert scan["rsi_min"] == 0.0, scan


# --- 2 · the full condition, from the rule itself -------------------------

def test_both_terms_is_the_shipped_rules_own_enter():
    """Exactly one of the four tapes satisfies `rsi < RSI_MAX and NOT uptrend
    and v > 0`, and `both_terms_n` reports the count `signals()` itself
    produced — never a condition retyped in the census."""
    b = _drive(["down", "down_rally", "up_dip", "up"])
    scan = fam._census_extra(b)["scan"]
    assert scan["both_terms_n"] == 1, scan
    # two entering coins => two, so the field is a COUNT and not a flag
    b2 = _drive(["down", "down", "up"])
    assert fam._census_extra(b2)["scan"]["both_terms_n"] == 2


def test_both_terms_is_never_larger_than_the_terms_it_conjoins():
    """A conjunction cannot outnumber either conjunct. Cheap, and it is the
    arithmetic that catches a count wired to the wrong map."""
    b = _drive(["down", "down", "down_rally", "up_dip", "up"])
    scan = fam._census_extra(b)["scan"]
    assert scan["both_terms_n"] <= scan["outside_uptrend_n"] <= scan["rsi_read"]
    assert scan["both_terms_n"] <= scan["near_bar"]


# --- 3 · the fail-safe half -----------------------------------------------

def test_absent_rather_than_zero_when_nothing_was_read():
    """`outside_uptrend_n: 0` on an unread universe reads as "every coin is in
    an uptrend" — a measurement, from no data. Absence is the honest degrade
    (I8), the same rule `(rr)`'s gauge already follows."""
    b = _B(_mum())
    scan = fam._census_extra(b)["scan"]
    for k in ("outside_uptrend_n", "both_terms_n"):
        assert k not in scan, f"{k} was invented from an empty reading set"


def test_a_non_bool_uptrend_is_never_read_as_OUTSIDE():
    """`False` here means the trend term PASSES. So a None/absent uptrend must
    not reach the map at all — coercing it would publish a fabricated pass,
    which is the direction that would argue FOR a widening on no evidence."""
    b = _B(_mum())
    for coin, sig in (("A", {"rsi": 10.0, "uptrend": None}),
                      ("B", {"rsi": 10.0}),
                      ("C", {"rsi": 10.0, "uptrend": "no"})):
        if sig and isinstance(sig.get("uptrend"), bool):
            b.last_uptrend[coin] = sig["uptrend"]
    assert b.last_uptrend == {}
    assert "outside_uptrend_n" not in fam._census_extra(b)["scan"]


# --- 4 · the loop feeds both maps -----------------------------------------

def _assigned_subscripts(attr):
    """Every `<x>.<attr>[...] = ...` in the module, as (source line) nodes."""
    tree = ast.parse((ROOT / "lighter_family_bot.py").read_text())
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for t in node.targets:
            if (isinstance(t, ast.Subscript)
                    and isinstance(t.value, ast.Attribute)
                    and t.value.attr == attr):
                out.append(node)
    return out


def test_the_scan_loop_actually_feeds_both_maps():
    """A gauge with no feeder is the registered-but-inert shape (I18): it
    publishes nothing forever and reads as "no readings", i.e. the exact
    silence it exists to break. On the AST, not a substring — a substring test
    is not a wiring test, and this one would pass against the comment."""
    for attr in ("last_uptrend", "last_enter"):
        nodes = _assigned_subscripts(attr)
        assert nodes, f"nothing in the scan loop ever writes b.{attr}"
        # and the value assigned must come from the strategy's own sig dict
        for n in nodes:
            names = {x.id for x in ast.walk(n.value) if isinstance(x, ast.Name)}
            assert "sig" in names, \
                f"b.{attr} is fed from something other than signals()' output"


def test_the_uptrend_capture_keeps_its_bool_guard():
    """The capture's fail-safe, pinned where it LIVES rather than where this
    file re-enacts it: drop the `isinstance(..., bool)` and a None/absent
    uptrend becomes `False`, i.e. "outside an uptrend" — a fabricated PASS on
    the very term a widening would be argued from."""
    guarded = 0
    tree = ast.parse((ROOT / "lighter_family_bot.py").read_text())
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        tgts = {t.value.attr for a in node.body
                if isinstance(a, ast.Assign)
                for t in a.targets
                if isinstance(t, ast.Subscript)
                and isinstance(t.value, ast.Attribute)}
        if "last_uptrend" not in tgts:
            continue
        calls = [c for c in ast.walk(node.test)
                 if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)
                 and c.func.id == "isinstance"]
        assert calls, "b.last_uptrend is written with no isinstance guard"
        assert any(isinstance(a, ast.Name) and a.id == "bool"
                   for c in calls for a in c.args), \
            "the guard admits something other than a bool"
        guarded += 1
    assert guarded == 1, f"expected one capture site, found {guarded}"


def test_the_publish_path_wires_the_series():
    """Both halves, or the series is inert: the loop must SNAPSHOT the census
    every cycle and the row must PUBLISH the rollup. Either one missing and
    `census_24h` reads as "this book has no history" forever — the (lv)
    ambiguity the whole instrument exists to remove."""
    tree = ast.parse((ROOT / "lighter_family_bot.py").read_text())
    fns = {n.name: n for n in ast.walk(tree)
           if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    loop = fns["main"]
    calls = [c for c in ast.walk(loop) if isinstance(c, ast.Call)]
    assert any(isinstance(c.func, ast.Attribute)
               and c.func.attr == "snapshot_census" for c in calls), \
        "the loop never snapshots the census — nothing accumulates"
    assert any(isinstance(c.func, ast.Name)
               and c.func.id == "_census_series_extra" for c in calls), \
        "the row never publishes census_24h"
    # and the snapshot is fed by the ONE owner, not a second census
    snap = [c for c in calls if isinstance(c.func, ast.Attribute)
            and c.func.attr == "snapshot_census"]
    src = (ROOT / "lighter_family_bot.py").read_text().splitlines()
    window = "\n".join(src[max(0, snap[0].lineno - 6):snap[0].lineno])
    assert "_census_extra(b)" in window, \
        "the stored census is not the published one"


def test_the_carrier_still_emits_both_terms_on_a_NO_ENTRY_bar():
    """The other half of the feeder contract: the no-entry case is the only
    one these gauges exist to measure, so `signals()` must report `uptrend`
    (and `enter: None`) rather than returning early."""
    sig = _mum().signals(_bars(_tape("down_rally")), {})
    assert sig["enter"] is None, "fixture must be the NO-ENTRY case"
    assert isinstance(sig.get("uptrend"), bool)


# --- 5 · census_24h, the denominator --------------------------------------

class FakeHistory:
    """bot_state_history at the save/fetch seam, replaying
    `fetch_state_history`'s own contract — NEWEST FIRST, [{"ts": iso,
    "payload": dict}], limit slicing included."""

    def __init__(self):
        self.rows = []

    def save(self, key, payload, at=None):
        self.rows.append((key, time.time() if at is None else at, payload))
        return True

    def fetch(self, key, limit=800):
        import datetime as dt
        got = sorted([r for r in self.rows if r[0] == key],
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


def test_the_census_accumulates_over_loops_and_publishes_a_denominator(hist):
    """THE POINT of the series: `no_signal: 3` on one loop and on 40 of them
    are the same integer and opposite facts. The stored payload is the ONE
    owner's own output (`_census_extra`), not a dict shaped like it."""
    b = _drive(["down", "down_rally", "up_dip", "up"])
    b.scan["no_signal"] = 2
    b.scan["uptrend_blocked"] = 1
    scan = fam._census_extra(b)["scan"]
    for _ in range(5):
        assert store.snapshot_census(b.bot_id, scan) is True
    # keys stored are the publisher's own keys — rule 3 made executable
    assert set(hist.rows[0][2]) - {store.CENSUS_DROPPED_KEY} == set(scan)

    out = fam._census_series_extra(b, time.time())
    w = out["census_24h"]
    assert w["loops"] == 5, w
    assert w["no_signal"] == 10 and w["uptrend_blocked"] == 5, w
    assert w["outside_uptrend_n"] == 10 and w["both_terms_n"] == 5, w
    assert w["binding_gate"] == "no_signal", w
    assert w["age_s"] == 0, w


def test_a_dark_db_changes_nothing(monkeypatch):
    """No DATABASE_URL under pytest, so this is the real dark path: the rollup
    is OMITTED rather than published as a zero-filled dict, and the snapshot
    is a no-op that raises nothing into a trading loop."""
    b = _drive(["down", "up"])
    assert fam._census_series_extra(b, time.time()) == {}
    assert store.snapshot_census(b.bot_id, fam._census_extra(b)["scan"]) is False


def test_a_reader_that_raises_never_reaches_the_trading_loop(monkeypatch):
    def _boom(*_a, **_k):
        raise RuntimeError("history read failed")
    monkeypatch.setattr(store, "census_window", _boom)
    assert fam._census_series_extra(_drive(["down"]), time.time()) == {}


def test_the_rollup_is_cached_and_carries_its_own_age(hist):
    """A cache that quietly froze would be I1 living inside the instrument
    built to answer I18 — so the served rollup stamps how old it is, and the
    recompute is bounded by CENSUS_ROLLUP_S rather than run every 90s loop."""
    b = _drive(["down", "up"])
    store.snapshot_census(b.bot_id, fam._census_extra(b)["scan"])
    t0 = time.time()
    assert fam._census_series_extra(b, t0)["census_24h"]["loops"] == 1

    calls = []
    real = store.census_window
    def _counted(bot, *a, **k):
        calls.append(bot)
        return real(bot, *a, **k)
    store.census_window = _counted
    try:
        # inside the window: served from cache, and the age is VISIBLE
        served = fam._census_series_extra(b, t0 + 60.0)["census_24h"]
        assert calls == [], "the rollup was recomputed inside its own window"
        assert served["age_s"] == 60, served
        # past it: recomputed
        fam._census_series_extra(b, t0 + fam.CENSUS_ROLLUP_S + 1.0)
        assert calls == [b.bot_id], calls
    finally:
        store.census_window = real


# --- 6 · blast radius, and publish-only -----------------------------------

def test_no_other_family_book_grows_these_fields():
    """`uptrend` means the OPPOSITE thing on 🙏 SwingDip (required, not
    blocking), so the semantics are the carrier's — never the dict's shape.
    Gated on UPTREND_BLOCKS, exactly as `census_no_entry_why` is."""
    for s in fam.STRATEGIES:
        if getattr(s, "UPTREND_BLOCKS", False):
            continue
        b = _B(s)
        b.last_uptrend = {"A": False, "B": True}
        b.last_enter = {"A": True, "B": False}
        scan = fam._census_extra(b).get("scan", {})
        assert "outside_uptrend_n" not in scan, s.bot
        assert "both_terms_n" not in scan, s.bot


def test_a_census_book_that_is_not_mum_still_gets_its_series(hist):
    """The SERIES is not mum-scoped — 🙏 avo and 🔮 georgia declare `census`
    too, and their refusals need a denominator just as much."""
    others = [s for s in fam.STRATEGIES
              if getattr(s, "census", False)
              and not getattr(s, "UPTREND_BLOCKS", False)]
    assert others, "no non-mum census book to check"
    b = _B(others[0])
    b.scan = {"scanned": 7, "no_signal": 7, "opened": 0}
    store.snapshot_census(b.bot_id, fam._census_extra(b)["scan"])
    assert fam._census_series_extra(b, time.time())["census_24h"]["loops"] == 1


def test_a_non_census_book_publishes_no_series(hist):
    non = [s for s in fam.STRATEGIES if not getattr(s, "census", False)]
    assert non, "every strategy declares a census — this arm is vacuous"
    b = _B(non[0])
    assert fam._census_series_extra(b, time.time()) == {}


def test_it_is_publish_only():
    """(vm) adds counters and a report. No gate's behaviour may differ, so no
    new field may be READ anywhere: the entry condition is `signals()`' own
    `enter`, unchanged, and nothing consumes `census_24h`."""
    src = (ROOT / "lighter_family_bot.py").read_text()
    tree = ast.parse(src)
    for field in ("outside_uptrend_n", "both_terms_n", "census_24h"):
        # the ONLY occurrences are the census literals that WRITE them
        loads = [n for n in ast.walk(tree)
                 if isinstance(n, ast.Subscript)
                 and isinstance(n.slice, ast.Constant)
                 and n.slice.value == field
                 and isinstance(n.ctx, ast.Load)]
        assert not loads, f"{field} is being read back — a counter grew a gate"
    # ...and the maps behind them are touched by exactly three places: the
    # Book that owns them, the scan loop that fills them, and the census that
    # reports them. Anything else naming one is a consumer, and a consumer is
    # how a counter becomes a gate.
    maps = {"last_uptrend", "last_enter"}
    #: the census OWNS the read; the Book declares them; every other function
    #: — `main` included, where the trading decisions actually are — may only
    #: WRITE. `b.last_enter[coin] = ...` is a Subscript in Store context; any
    #: other use is a consumer, and a consumer is how a counter becomes a gate.
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if fn.name in ("__init__", "_census_extra"):
            continue
        stores = {id(n.value) for n in ast.walk(fn)
                  if isinstance(n, ast.Subscript)
                  and isinstance(n.ctx, ast.Store)
                  and isinstance(n.value, ast.Attribute)
                  and n.value.attr in maps}
        for n in ast.walk(fn):
            if isinstance(n, ast.Attribute) and n.attr in maps:
                assert id(n) in stores, \
                    f"{fn.name} READS b.{n.attr} — a counter grew a consumer"
