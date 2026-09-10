"""[2026-09-10 (zr)] 👩 MUM'S OVERSOLD-BREADTH FLOOR — the instrument, the
inert gate, and the judge candidate.

Eamon: *"Fix mum real money and shadow bot."* The day's loss (six −4% stops in
75 minutes) was the designed exposure, not a defect — but the autopsy found
where her edge actually lives: on BOTH arms, closes opened in a same-loop
batch of ≥3 coins read +1.1%/trade with a 2–3% stop rate, while closes opened
alone or in a pair read ≈0 with 10–17% stops. Four of the six stops were
single/pair entries. And the honest statistic is SMALLER than the per-trade t
says: the batches are SEVEN open-events on the live arm and a permutation of
event sizes reads P≈0.10 — hypothesis-grade (I21/(kw)/(ky)), which is why the
floor ships INERT and reaches real money only through the judge.

WHAT THESE TESTS GUARD, in the order the damage would be worst:
  1  SHIPPED INERT. `BREADTH_MIN` is 1 on the class and in both registry
     lanes; a coin that enters is itself breadth 1, so the shipped default can
     never refuse an entry. Registering a lever moves nothing ((it)).
  2  RESTRICT-ONLY and FAIL-CLOSED when armed: the gate is a conjunct beside
     `enter`, it can only remove, and an armed floor that cannot measure
     refuses rather than falling through to the unfiltered rule ((xl)).
  3  ONE OWNER, SAME RUNG ON BOTH HOSTS. The pre-pass, the decision and the
     stamp are `lighter_family_bot`'s and the live host imports them; both
     entry loops ask the gate right after the coin's own signal.
  4  THE RECORD. `breadth_n` is stamped at the OPEN on both hosts and copied
     to the close row, the census publishes the gauge whether or not the
     floor is armed, and the refusal is DECLARED so `binding_gate` can name it.
  5  THE JUDGE CAN DRIVE IT. Registered, caged, consumed via MUM_LEVER_ATTRS,
     receipted by `mum_bars`, mapped xp→live, and queued as `mum-breadth-3`
     BEHIND the running candidate — never pre-empting it.
"""
import copy
import random
import sys
from pathlib import Path

import pytest

ROOT = str(Path(__file__).resolve().parents[2])
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import bot_pnl_store as store        # noqa: E402
import experiment_judge as ej        # noqa: E402
import fleet_tuning as ft            # noqa: E402
import lighter_family_bot as fb      # noqa: E402

pytestmark = pytest.mark.autonomy


def _mum():
    return next(s for s in fb.STRATEGIES if s.bot == "freqtrade-mum")


def _tape(n=500, seed=11):
    """A downtrend with real dips (the (xl) fixture): her cell fires on some
    seeds' LAST candle and not on others, which is exactly the split a breadth
    count needs."""
    rnd = random.Random(seed)
    px, c, v = 100.0, [], []
    for _ in range(n):
        px *= 1 - 0.0015 + rnd.gauss(0, 0.018)
        c.append(px)
        v.append(1.0)
    return {"c": c, "h": c, "l": c, "v": v, "t": list(range(n))}


def _last_enters(st, bars):
    sig = st.signals(bars, {})
    return bool(sig and sig.get("enter"))


def _universe(st, want_in=3, want_out=2, seeds=range(1, 200)):
    """Coins whose last candle enters / does not, found rather than assumed —
    a fixture that never fires makes every assertion below vacuous."""
    ins, outs = {}, {}
    for seed in seeds:
        bars = _tape(seed=seed)
        if _last_enters(st, bars):
            if len(ins) < want_in:
                ins[f"IN{len(ins)}"] = bars
        elif len(outs) < want_out:
            outs[f"OUT{len(outs)}"] = bars
        if len(ins) == want_in and len(outs) == want_out:
            break
    assert len(ins) == want_in and len(outs) == want_out, (
        "the tape never produced the split — every other test here would be "
        "vacuously green")
    return ins, outs


def _armed(bar):
    st = copy.copy(_mum())
    st.BREADTH_MIN = bar
    return st


# ------------------------------------------------------------- 0 · the fixture
def test_the_fixture_actually_fires():
    ins, outs = _universe(_mum())
    assert len(ins) == 3 and len(outs) == 2


# ------------------------------------------------------------ 1 · shipped inert
def test_the_shipped_default_is_inert_on_the_class_and_in_both_lanes():
    cls = type(_mum())
    assert cls.BREADTH_MIN == 1
    for lane in ("xp", "live"):
        spec = ft.LEVERS[f"{lane}.mum.breadth_min"]
        assert spec["env_default"] == 1 and spec["kind"] == "int"
        # the cage's floor IS the inert value: the rail can only tighten
        assert spec["lo"] == 1 and spec["hi"] >= 3


def test_an_inert_floor_never_refuses_whatever_the_breadth_reads():
    st = _mum()
    for breadth in ({"n": 0, "read": 0, "of": 5}, {"n": 1}, {"n": 9},
                    None, {"n": "junk"}):
        assert fb.breadth_thin(st, breadth) is False, breadth


# --------------------------------------------------- 2 · armed: restrict, closed
def test_an_armed_floor_refuses_below_the_bar_and_admits_at_it():
    st = _armed(3)
    assert fb.breadth_thin(st, {"n": 2}) is True
    assert fb.breadth_thin(st, {"n": 3}) is False
    assert fb.breadth_thin(st, {"n": 7}) is False


def test_an_armed_floor_that_cannot_measure_refuses():
    """Fail-CLOSED, the (xl) shape: armed but unreadable must not fall through
    to the unfiltered rule."""
    st = _armed(3)
    assert fb.breadth_thin(st, None) is True
    assert fb.breadth_thin(st, {"n": "junk"}) is True
    assert fb.breadth_thin(st, {}) is True


def test_a_junk_bar_reads_as_inert_not_as_armed():
    st = copy.copy(_mum())
    st.BREADTH_MIN = "not a number"
    assert fb.breadth_thin(st, {"n": 0}) is False


def test_a_carrier_without_the_knob_is_never_measured_and_never_refused():
    avo = next(s for s in fb.STRATEGIES if s.bot == "freqtrade-avo-maria")
    ins, _ = _universe(_mum())
    assert fb.oversold_breadth(avo, list(ins), ins.get) is None
    assert fb.breadth_thin(avo, None) is False
    assert fb.breadth_n_of(None) is None


# ------------------------------------------------------------ 3 · the pre-pass
def test_breadth_counts_every_coin_whose_last_candle_enters():
    st = _mum()
    ins, outs = _universe(st)
    coins = {**ins, **outs}
    out = fb.oversold_breadth(st, list(coins), coins.get)
    assert out == {"n": 3, "read": 5, "of": 5}
    # a subset moves the count with it — the number is the coins, not the slots
    assert fb.oversold_breadth(st, list(outs), coins.get) == {"n": 0, "read": 2, "of": 2}
    assert fb.breadth_n_of(out) == 3


def test_an_unreadable_coin_is_neither_counted_nor_read():
    st = _mum()
    ins, outs = _universe(st)
    short = _tape(n=50)                       # below min_bars: signals -> None
    coins = {**ins, **outs, "SHORT": short, "NOBARS": None,
             "NOT": {"c": [1.0], "h": [1.0], "l": [1.0], "v": [1.0]}}
    out = fb.oversold_breadth(st, list(coins), coins.get)
    assert out == {"n": 3, "read": 5, "of": 8}


def test_a_broken_bar_source_or_rule_never_raises():
    st = _mum()

    def boom(_coin):
        raise RuntimeError("venue down")
    assert fb.oversold_breadth(st, ["A", "B"], boom) == {"n": 0, "read": 0, "of": 2}


def test_the_memo_reuses_a_verdict_only_for_the_same_candle_under_the_same_bars():
    st = copy.copy(_mum())
    ins, outs = _universe(st)
    coins = {**ins, **outs}
    calls = {"n": 0}
    real = st.signals

    def counting(bars, extra):
        calls["n"] += 1
        return real(bars, extra)
    st.signals = counting
    memo = {}
    first = fb.oversold_breadth(st, list(coins), coins.get, memo=memo)
    assert calls["n"] == 5 and first["n"] == 3
    # same candle, same bars: nothing re-evaluated, same answer
    again = fb.oversold_breadth(st, list(coins), coins.get, memo=memo)
    assert calls["n"] == 5 and again == first
    # a lever moves mid-hour: every coin re-evaluated under the new bar
    st.RSI_MAX = float(st.RSI_MAX) + 1.0
    fb.oversold_breadth(st, list(coins), coins.get, memo=memo)
    assert calls["n"] == 10
    # a new candle on one coin: that coin alone re-evaluated
    coins["IN0"] = dict(coins["IN0"], t=list(range(1, 501)))
    fb.oversold_breadth(st, list(coins), coins.get, memo=memo)
    assert calls["n"] == 11


# ------------------------------------------ 4 · the record, on both hosts
def _segment(src, start, end):
    i = src.index(start)
    j = src.index(end, i)
    return src[i:j]


def test_both_hosts_ask_the_gate_at_the_same_rung_and_stamp_the_count():
    """Scoped to each host's ENTRY LOOP, never a page-wide substring (the
    doctrine's structural-claim rule). Both arms must refuse right after the
    coin's own signal, and both must record `breadth_n` at the open."""
    fam = Path(ROOT, "lighter_family_bot.py").read_text()
    live = Path(ROOT, "lighter_avo_live_bot.py").read_text()
    shadow_loop = _segment(fam, "for coin in shadow_scan_order(b.coins, list(b.broker.pos), _rets):",
                           "# [2026-07-16 ZOMBIE GUARD] ORPHANS:")
    live_loop = _segment(live, "for sym in diversified_order(universe, list(pos), _rets):",
                         "scan_verdict.update(cycle_verdict)")
    # the gate, right after the signal verdict on each host
    s_sig = shadow_loop.index("b.scan[census_no_entry_why(b.s, sig)] += 1")
    s_gate = shadow_loop.index("if breadth_thin(b.s, b.breadth):")
    s_lock = shadow_loop.index("if locked:")
    assert s_sig < s_gate < s_lock, "the shadow's gate is not at the signal rung"
    l_sig = live_loop.index("_verdict(sym, census_no_entry_why(S, sig), sig=sig)")
    l_gate = live_loop.index("if _fam_breadth_thin(S, breadth_now):")
    l_px = live_loop.index("px = marks.fresh_mid(venue, sym)")
    assert l_sig < l_gate < l_px, "the live host's gate is not at the signal rung"
    assert '_verdict(sym, "breadth_thin")' in live_loop
    assert 'b.scan["breadth_thin"] += 1' in shadow_loop
    # the stamp at the open, on both
    assert '"breadth_n": breadth_n_of(b.breadth)' in shadow_loop
    assert '"breadth_n": _fam_breadth_n_of(breadth_now)' in live_loop
    # the pre-pass runs BEFORE either loop, off the ONE owner
    assert "b.breadth = oversold_breadth(" in fam[:fam.index(
        "for coin in shadow_scan_order(b.coins, list(b.broker.pos), _rets):")]
    assert "breadth_now = _fam_oversold_breadth(" in live[:live.index(
        "for sym in diversified_order(universe, list(pos), _rets):")]
    # ...and the live host IMPORTS the owner rather than re-typing it
    imports = _segment(live, "from lighter_family_bot import (",
                       "from venues import marks")
    for name in ("oversold_breadth", "breadth_thin", "breadth_n_of"):
        assert name in imports, f"{name} is not imported from the owner"


def test_the_close_row_copies_the_open_stamp_on_both_hosts():
    fam = Path(ROOT, "lighter_family_bot.py").read_text()
    live = Path(ROOT, "lighter_avo_live_bot.py").read_text()
    rc = _segment(fam, "    def record_close(self, coin, px, price_pnl, reason",
                  "\ndef btc_regime_up(")
    bc = _segment(live, "def _book_close(sym, exit_px, measured, why, reason):",
                  '"mmf_factor": m.get("mmf_factor"),')
    for seg in (rc, bc):
        assert '"breadth_n": m["breadth_n"]' in seg
        assert 'm.get("breadth_n") is not None' in seg, (
            "the close must copy the OPEN's stamp and omit it when absent — "
            "never fabricate a 0")


def test_the_shadow_census_publishes_the_gauge_armed_or_not():
    st = _mum()
    ins, outs = _universe(st)
    coins = {**ins, **outs}
    b = fb.Book(st, "lighter_shadow", list(coins))
    # nothing measured yet: the gauge is ABSENT, never 0 (the census nests
    # its gauges under `scan`, the key the row publishes)
    ex = fb._census_extra(b)["scan"]
    assert "breadth_n" not in ex and "breadth_min" not in ex
    b.breadth = fb.oversold_breadth(st, list(coins), coins.get, memo=b.breadth_memo)
    ex = fb._census_extra(b)["scan"]
    assert (ex["breadth_n"], ex["breadth_read"], ex["breadth_min"]) == (3, 5, 1)
    b.s = _armed(3)
    assert fb._census_extra(b)["scan"]["breadth_min"] == 3


def test_the_live_census_publishes_the_same_three_keys():
    import lighter_avo_live_bot as live
    st = _mum()
    out = live.scan_census({}, {}, None, ["A", "B"], [], None, None, None, None, 0.0,
                           strategy=st, breadth={"n": 4, "read": 80, "of": 86})
    assert (out["breadth_n"], out["breadth_read"], out["breadth_min"]) == (4, 80, 1)
    out = live.scan_census({}, {}, None, ["A", "B"], [], None, None, None, None, 0.0,
                           strategy=st, breadth=None)
    assert "breadth_n" not in out and "breadth_min" not in out


def test_the_shadow_scan_init_carries_the_bucket_and_it_is_declared():
    fam = Path(ROOT, "lighter_family_bot.py").read_text()
    init = _segment(fam, 'b.scan = {"scanned": 0,', "}")
    assert '"breadth_thin": 0' in init
    assert "breadth_thin" in store.CENSUS_REFUSALS
    assert "breadth_thin" not in store.CENSUS_DENOMINATORS


# -------------------------------------------------- 5 · the judge can drive it
def test_the_lever_is_consumed_receipted_and_cast_to_an_int(monkeypatch):
    assert ("breadth_min", "BREADTH_MIN", int) in fb.MUM_LEVER_ATTRS
    st = copy.copy(_mum())
    assert fb.mum_bars(st)["breadth_min"] == 1.0
    assert fb.mum_env_defaults(st)["breadth_min"] == 1.0
    monkeypatch.setattr(ft, "get_lever",
                        lambda name, default, **kw: 3.0 if name.endswith("breadth_min") else default)
    moved = fb.apply_book_levers(st, "xp.mum.")
    assert moved == {"xp.mum.breadth_min": 3.0}
    assert st.BREADTH_MIN == 3 and isinstance(st.BREADTH_MIN, int)
    assert fb.mum_bars(st)["breadth_min"] == 3.0
    assert type(st).BREADTH_MIN == 1, "the overlay mutated the CLASS"
    # expiry reverts cleanly from the class default
    monkeypatch.setattr(ft, "get_lever", lambda name, default, **kw: default)
    assert fb.apply_book_levers(st, "xp.mum.") == {}
    assert st.BREADTH_MIN == 1


def test_the_lever_is_registered_caged_mapped_and_judge_owned():
    xk, lk = "xp.mum.breadth_min", "live.mum.breadth_min"
    assert ft.LEVERS[xk]["lane"] == "lighter-xp"
    assert ft.LEVERS[lk]["lane"] == "lighter-live"
    assert ft.clamp(xk, 3) == 3 and ft.clamp(lk, 3) == 3
    assert ft.clamp(xk, 0) == 1, "the cage must not reach below the inert value"
    assert ej.XP_TO_LIVE[xk] == lk
    assert ej.LIVE_ENV_DEFAULTS[lk] == (1.0, "up"), (
        "a HIGHER floor admits FEWER entries — tighter is 'up', and the release "
        "paths consume that direction")
    for author in ft.AUTHOR_LANES:
        assert ft._author_may_write(lk, "lighter-live", author) == \
            (author == "experiment-judge"), (lk, author)


def test_the_candidate_is_queued_behind_the_running_one_and_inside_the_cage():
    names = [c["name"] for c in ej.MUM_CANDIDATES]
    assert names.index("mum-breadth-3") == names.index("mum-vel-12-20") + 1, (
        "breadth-3 must queue BEHIND vel-12-20, never pre-empt it")
    cand = next(c for c in ej.MUM_CANDIDATES if c["name"] == "mum-breadth-3")
    assert cand["levers"] == {"xp.mum.breadth_min": 3.0}
    for k, v in cand["levers"].items():
        assert ft.clamp(k, v) == v and ft.clamp(ej.XP_TO_LIVE[k], v) == v


def test_a_close_taken_under_the_candidate_carries_a_receipt_the_judge_accepts():
    st = _armed(3)
    row = {"extra": {"bars": fb.mum_bars(st)}}
    assert ej.ran_candidate(row, {"xp.mum.breadth_min": 3.0})
    assert not ej.ran_candidate({"extra": {"bars": fb.mum_bars(_mum())}},
                                {"xp.mum.breadth_min": 3.0})


def test_the_quantity_the_floor_cuts_has_a_measurement_path():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "ala", Path(ROOT, "scripts", "audit_lever_authority.py"))
    ala = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ala)
    for key, bot in (("xp.mum.breadth_min", "freqtrade-mum-lshadow"),
                     ("live.mum.breadth_min", "freqtrade-mum-lighter")):
        q = ala.QUANTITIES[key]
        assert q["source"] == f"ledger:{bot}"
        assert q["extract"] == ("xfield", ("breadth_n", None))
        assert q["dir"] == "ge"
