"""[(sk)] 🌾 carry's liquidity gate stops PROXYING and starts MEASURING.

THE CAGE. The fleet's best-evidenced book (n=101, +$66.21, the only one that has
ever cleared the `t` bar) was holding **0 of 12 slots** with **`eligible: 0` of
228 books scanned**. Its `CARRY_MIN_VOL` floor exists because *"per-book
slippage here is unmeasured"* — the floor is not a view about turnover, it is a
stand-in for a cost nobody had measured.

Measured 2026-08-20 by `scripts/study_depth_vs_volume.py`, walking the live book
both ways for this book's own clip through the fleet's own fill model: of the 20
books over the 20% TRUE APR bar the $1M floor refused SIXTEEN, and every one of
the sixteen filled an $80 clip out of visible depth and repaid its measured
round trip inside the max hold. XMR (a third of PUMP's turnover) costs 5.1bps
against PUMP's 9.4; UNITREE repays 15x faster than PUMP and was refused while
PUMP was admitted. On a clip this size the floor protects against a size the
book has never traded.

WHAT THESE TESTS PIN, and why each is a separate failure:

  1. the FAST PATH is untouched — a coin at or above the floor is admitted
     exactly as before, with no book read at all;
  2. the ESCAPE admits on MEASURED payback and refuses when the clip cannot be
     filled or the carry cannot repay it;
  3. FAIL-CLOSED on every uncertainty, because this AUTHORISES an entry
     (the `lens_wins` precedent, I15);
  4. the CENSUS and the CANDIDATE EXPRESSION ask the SAME question — a census
     that can drift from the gate it explains is worse than no census;
  5. the probe is BOUNDED and never fires on a coin whose decision it cannot
     change;
  6. the kill switch restores the old behaviour EXACTLY;
  7. the rail can reach it (I18) and the cost model has ONE OWNER.
"""
import time

import pytest

pytestmark = pytest.mark.autonomy

import funding_carry_bot as C            # noqa: E402


# --------------------------------------------------------------------- books

def book(spread_bps=10.0, depth_usd=1e6, px=100.0):
    """A two-sided book with `depth_usd` a side at `spread_bps` wide."""
    half = px * spread_bps / 2e4
    sz = depth_usd / px
    return {"bids": [(px - half, sz)], "asks": [(px + half, sz)]}


EMPTY = {"bids": [], "asks": []}


class _Venue:
    def __init__(self, books=None, raises=False):
        self.books, self.raises, self.calls = books or {}, raises, []

    def orderbook(self, coin):
        self.calls.append(coin)
        if self.raises:
            raise RuntimeError("venue down")
        return self.books.get(coin)


class _Ctx:
    def __init__(self, venue):
        self.venue = venue


# ------------------------------------------------------------ 1 · the metric

def test_the_round_trip_is_both_crossings_of_the_same_mid():
    # 10bps wide, clip fits at the top: in 5bps + out 5bps = 10bps.
    assert C.rt_cost_bps(book(spread_bps=10.0), 100.0) == pytest.approx(10.0)


def test_walking_deeper_into_the_book_costs_strictly_more():
    b = {"bids": [(99.0, 1.0), (95.0, 1000.0)],
         "asks": [(101.0, 1.0), (105.0, 1000.0)]}
    assert C.rt_cost_bps(b, 1000.0) > C.rt_cost_bps(b, 50.0)


def test_a_book_that_cannot_fill_the_clip_has_NO_price():
    """UNFILLABLE is a verdict, not a large number — a huge bps would still be
    a number a caller could compare, and comparing it is exactly wrong."""
    assert C.rt_cost_bps(book(depth_usd=10.0), 1e9) is None
    assert C.rt_cost_bps(EMPTY, 100.0) is None
    assert C.rt_cost_bps(None, 100.0) is None


def test_payback_is_inverse_in_the_rate():
    """The whole thesis: a 22bps round trip at 20% APR is a 96h wait and at
    1200% APR it is under two hours. The gate this replaces could not tell
    those two apart."""
    slow = C.payback_hours(22.0, 0.20)
    fast = C.payback_hours(22.0, 12.0)
    assert slow == pytest.approx(96.36, abs=0.1), slow
    assert fast == pytest.approx(1.606, abs=0.01), fast
    assert C.payback_hours(22.0, 0.0) is None
    assert C.payback_hours(None, 1.0) is None
    # sign-blind: a long_perp carry (negative rate) pays just as well
    assert C.payback_hours(22.0, -1.0) == C.payback_hours(22.0, 1.0)


# ------------------------------------------------------------- 2 · admission

def test_a_cheap_sub_floor_book_is_admitted_on_its_measured_payback():
    """KAITO's live shape: $226k of turnover — a quarter of the floor — 7.6bps
    round trip, 5.0h payback. Refused by turnover, admitted by measurement."""
    ctx = _Ctx(_Venue({"KAITO": book(spread_bps=7.6, depth_usd=5e5)}))
    ok, d = C.depth_admits(ctx, "KAITO", 1.31, 80.0)
    assert ok is True, d
    assert d["rt_bps"] == pytest.approx(7.6, abs=0.1)
    assert d["payback_h"] == pytest.approx(5.08, abs=0.1)
    assert d["why"] == "depth-admitted"


def test_a_carry_that_cannot_repay_its_own_fill_is_refused():
    """RAIL's live shape: $490 of turnover, 46.7bps round trip at 61% APR =
    66.8h. The flat floor refused this too — for the wrong reason, and it took
    fourteen good books with it."""
    ctx = _Ctx(_Venue({"RAIL": book(spread_bps=46.7, depth_usd=5e4)}))
    ok, d = C.depth_admits(ctx, "RAIL", 0.613, 80.0, payback_max_h=48.0)
    assert ok is False and d["why"] == "payback-too-slow", d
    assert d["payback_h"] > 48.0


def test_the_bound_is_the_lever_not_a_constant():
    ctx = _Ctx(_Venue({"X": book(spread_bps=46.7, depth_usd=5e4)}))
    assert C.depth_admits(ctx, "X", 0.613, 80.0, payback_max_h=48.0)[0] is False
    assert C.depth_admits(ctx, "X", 0.613, 80.0, payback_max_h=96.0)[0] is True


# ----------------------------------------------------------- 3 · fail-closed

@pytest.mark.parametrize("venue,why", [
    (_Venue({}, raises=True), "book-error:RuntimeError"),
    (_Venue({"X": EMPTY}), "unfillable"),
    (_Venue({"X": None}), "unfillable"),
    (_Venue({"X": book(depth_usd=1.0)}), "unfillable"),
])
def test_every_uncertainty_refuses(venue, why):
    """This function's True opens a position. Absence of evidence never
    authorises one (the (hs) rule, and I15's fail-CLOSED expand direction)."""
    ok, d = C.depth_admits(_Ctx(venue), "X", 1.0, 80.0)
    assert ok is False and d["why"] == why, d


def test_a_zero_rate_refuses_rather_than_dividing_by_zero():
    ctx = _Ctx(_Venue({"X": book()}))
    ok, d = C.depth_admits(ctx, "X", 0.0, 80.0)
    assert ok is False and d["why"] == "no-payback", d


# ---------------------------------------------------- 4 · census == the gate

def _fund(vol, rate=0.01):
    return {"rate": rate, "vol": vol, "mark": 100.0}


def test_the_census_counts_a_depth_admitted_coin_as_eligible():
    """The buckets must describe the decision the trading path takes. A coin
    the gate will trade must not be reported `thin`."""
    t0 = time.time()
    fund = {"CHEAP": _fund(2e5), "RICH": _fund(5e6)}
    hot = {"CHEAP": t0 - 99 * 3600, "RICH": t0 - 99 * 3600}
    seen = []

    def depth_ok(c, f):
        seen.append(c)
        return True

    out = C.scan_census(fund, {}, hot, t0, 1095.0, 0.20, min_vol=1e6,
                        persist_h=12.0, class_ok=lambda c: True,
                        depth_ok=depth_ok)
    assert out["eligible"] == 2 and out["thin"] == 0, out
    assert out["depth_admitted"] == 1, out
    assert seen == ["CHEAP"], "the above-floor coin must not cost a book read"


def test_the_buckets_still_partition_the_scan():
    """`depth_admitted` is a SUB-COUNT, never a bucket — the same contract
    `waiting_admissible` keeps."""
    t0 = time.time()
    fund = {"A": _fund(2e5), "B": _fund(5e6), "C": _fund(5e6, rate=0.0),
            "D": _fund(2e5), "E": _fund(5e6)}
    hot = {k: t0 - 99 * 3600 for k in ("A", "B", "C", "D")}
    out = C.scan_census(fund, {"E": 1}, hot, t0, 1095.0, 0.20, min_vol=1e6,
                        persist_h=12.0, class_ok=lambda c: True,
                        depth_ok=lambda c, f: c == "A")
    parts = sum(out[k] for k in ("held", "thin", "cold", "waiting",
                                 "noncrypto", "eligible"))
    assert parts == out["scanned"] == 5, out
    assert out["depth_admitted"] == 1 and out["thin"] == 1, out


def test_the_probe_never_fires_on_a_coin_whose_decision_it_cannot_change():
    """A sub-floor coin that is still WAITING out its persistence, or that the
    class screen will refuse, is thin either way — probing it is a REST call
    that can only ever be discarded."""
    t0 = time.time()
    fund = {"WAITING": _fund(2e5), "NONCRYPTO": _fund(2e5)}
    hot = {"WAITING": t0 - 1 * 3600, "NONCRYPTO": t0 - 99 * 3600}
    seen = []
    out = C.scan_census(fund, {}, hot, t0, 1095.0, 0.20, min_vol=1e6,
                        persist_h=12.0,
                        class_ok=lambda c: c != "NONCRYPTO",
                        depth_ok=lambda c, f: seen.append(c) or True)
    assert seen == [], f"probed a coin it could not admit: {seen}"
    assert out["thin"] == 2 and out["depth_admitted"] == 0, out


def test_a_census_with_no_depth_callable_is_byte_identical_to_before():
    t0 = time.time()
    fund = {"A": _fund(2e5), "B": _fund(5e6)}
    hot = {k: t0 - 99 * 3600 for k in fund}
    out = C.scan_census(fund, {}, hot, t0, 1095.0, 0.20, min_vol=1e6,
                        persist_h=12.0, class_ok=lambda c: True)
    assert out["thin"] == 1 and out["eligible"] == 1, out
    assert out["depth_admitted"] == 0, out


# ------------------------------------------------------------- 5 · the budget

def test_the_probe_budget_is_per_loop_and_fails_closed_when_spent():
    ctx = _Ctx(_Venue({"X": book()}))
    b = {"left": 1}
    assert C.depth_admits(ctx, "X", 1.0, 80.0, budget=b)[0] is True
    assert b["left"] == 0 and b["used"] == 1
    ok, d = C.depth_admits(ctx, "X", 1.0, 80.0, budget=b)
    assert ok is False and d["why"] == "probe-budget", d
    assert len(ctx.venue.calls) == 1, "a spent budget must not read the venue"


# --------------------------------------------------------- 6 · the kill switch

def test_the_kill_switch_restores_the_flat_floor_exactly(monkeypatch):
    monkeypatch.setattr(C, "DEPTH_ADMIT", False)
    ctx = _Ctx(_Venue({"X": book()}))
    ok, d = C.depth_admits(ctx, "X", 12.0, 80.0)
    assert ok is False and d["why"] == "disabled", d
    assert ctx.venue.calls == [], "a disabled gate must not read the venue"


def test_the_gate_publishes_both_of_its_numbers():
    """An unpublished gate is the (lz)/(pf) class: a reader who sees only
    `min_vol` mis-derives which coins this book can take."""
    import ast
    import inspect
    src = inspect.getsource(C)
    tree = ast.parse(src)
    caps = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            keys = [k.value for k in node.keys if isinstance(k, ast.Constant)]
            if "min_vol" in keys and "enter_apr" in keys:
                caps = keys
    assert caps, "could not find the caps literal — scan is blind"
    assert "payback_max_h" in caps and "depth_admit" in caps, caps


# ------------------------------------------------- 7 · reach, and one owner

def test_the_rail_can_reach_the_only_lever_that_opens_this_book():
    """I18. `carry.min_vol`'s cage is one-sided in the TIGHTEN direction, so
    without this the growth rail had NO motion that could widen carry's intake
    — on the book with the fleet's best evidence and an empty slot list."""
    import fleet_tuning as ft
    lev = ft.LEVERS["carry.payback_max_h"]
    assert lev["lane"] == "lighter-books"
    assert lev["lo"] < lev["env_default"] < lev["hi"], lev
    assert lev["env_default"] == C.PAYBACK_MAX_H
    assert lev["step"] > 0, "the opening direction must be walkable"
    # and the consumer actually reads it, or it is registered-but-inert
    import inspect
    body = inspect.getsource(C.apply_tuning)
    assert "carry.payback_max_h" in body and "PAYBACK_MAX_H" in body
    assert C._ENV_DEFAULTS["PAYBACK_MAX_H"] == C.PAYBACK_MAX_H


def test_apply_tuning_actually_moves_the_bound(monkeypatch):
    class _T:
        @staticmethod
        def get_lever(name, default):
            return 96.0 if name == "carry.payback_max_h" else default

    monkeypatch.setattr(C, "tuning", _T)
    monkeypatch.setattr(C, "PAYBACK_MAX_H", 48.0)
    moved = C.apply_tuning()
    assert moved.get("carry.payback_max_h") == 96.0, moved
    assert C.PAYBACK_MAX_H == 96.0


def test_the_cost_model_has_exactly_one_owner():
    """The study that justified this change and the gate that enforces it must
    be the SAME function, by identity — a second copy is a second rule, and on
    a cost model it shows up as a study recommending books the book refuses."""
    import scripts.study_depth_vs_volume as S
    assert S._rt is C.rt_cost_bps
    assert S.payback_h is C.payback_hours


def test_this_book_cannot_touch_real_money():
    """The change is admissible as shadow BOOK LOGIC only because this module
    has no live arm at all: `main()` refuses every mode but lighter_shadow, and
    the real-money funding floors live in a different file entirely."""
    import inspect
    src = inspect.getsource(C.main)
    assert "lighter_shadow" in src
    for forbidden in ("live.funding", "LIGHTER_API_PRIVATE_KEY", "dry_run=False"):
        assert forbidden not in inspect.getsource(C), forbidden


def test_the_candidate_expression_asks_the_same_question_as_the_census():
    """The gap the tests above cannot see. `depth_admits` can be correct, the
    census can be correct, and the ENTRY expression can still read the flat
    floor alone — in which case nothing changes, every test above stays green,
    and the book keeps refusing sixteen tradeable books.

    `candidates` is built inside `main()`, so this is asserted on the
    expression rather than by driving it: the claim is a RELATIONSHIP — the
    turnover floor and the measured escape must be joined by OR, so a
    sub-floor coin can still be admitted — not that a name appears somewhere.
    """
    import ast
    import inspect
    tree = ast.parse(inspect.getsource(C.main).lstrip())
    found = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Assign)
                and any(getattr(t, "id", None) == "candidates"
                        for t in node.targets)):
            continue
        for gen in (n for n in ast.walk(node)
                    if isinstance(n, ast.GeneratorExp)):
            for cond in (c for g in gen.generators for c in g.ifs):
                for bo in (n for n in ast.walk(cond)
                           if isinstance(n, ast.BoolOp)
                           and isinstance(n.op, ast.Or)):
                    txt = ast.unparse(bo)
                    if "MIN_DAY_VOLUME" in txt and "_depth_ok" in txt:
                        found.append(txt)
    assert found, ("the entry expression does not join the turnover floor to "
                   "the measured escape with OR — a sub-floor coin can never "
                   "be admitted, whatever `depth_admits` decides")


def test_the_entry_path_and_the_census_share_one_decision():
    """Two probes would be two REST reads and — worse — two chances to
    disagree about the same coin, which is the drift the census's own contract
    forbids. Pinned as a relationship: the census must be handed the SAME
    callable the candidate expression calls."""
    import ast
    import inspect
    tree = ast.parse(inspect.getsource(C.main).lstrip())
    passed = [kw.value for n in ast.walk(tree)
              if isinstance(n, ast.Call)
              and getattr(n.func, "id", "") == "scan_census"
              for kw in n.keywords if kw.arg == "depth_ok"]
    assert passed, "scan_census is called without depth_ok — the census would "\
                   "report `thin` for coins the entry path trades"
    assert all(getattr(v, "id", None) == "_depth_ok" for v in passed), \
        [ast.unparse(v) for v in passed]


# ------------------------------------------- 8 · the lever can be MEASURED

def test_receipts_record_refusals_too_not_just_admissions():
    """The truncation trap. A bound profiled only on the probes it ADMITTED
    sees a distribution already cut at the bound, so every re-measure agrees
    with wherever the bound happens to sit and the lever can never be moved on
    evidence. Asserted structurally: the append must not sit under `if ok`.
    """
    import ast
    import inspect
    tree = ast.parse(inspect.getsource(C.main).lstrip())
    appends = [n for n in ast.walk(tree)
               if isinstance(n, ast.Call)
               and isinstance(n.func, ast.Attribute)
               and n.func.attr == "append"
               and getattr(n.func.value, "id", "") == "_depth_recs"]
    assert appends, "no probe receipt is recorded — the lever is unmeasurable"
    guarded = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        test = ast.unparse(node.test)
        if test.strip() != "ok":
            continue
        for a in appends:
            if node.lineno <= a.lineno <= (node.end_lineno or a.lineno):
                guarded.append(a.lineno)
    assert not guarded, (
        f"receipt append at line(s) {guarded} sits under `if ok:` — the "
        "distribution would be truncated at the bound being measured")


def test_the_receipts_reach_the_source_the_audit_reads():
    """A receipt nobody stores is a print statement."""
    import ast
    import inspect
    tree = ast.parse(inspect.getsource(C.main).lstrip())
    saved = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call)
             and getattr(n.func, "attr", "") == "save_state"
             and "depth_scan" in ast.unparse(n)]
    assert saved, "depth_scan is never written to the durable state key"

    import scripts.audit_lever_authority as A
    q = A.QUANTITIES["carry.payback_max_h"]
    assert q["extract"] == ("list", ("depth_scan", "payback_h")), q
    assert q["source"].endswith("perps-funding-carry-lshadow"), q
    assert q["unit"] == "hours", q
