#!/usr/bin/env python3
"""[2026-08-22 (st)] A BOOK MUST BE ABLE TO SAY WHY IT DID NOT TRADE.

Eamon, 22-Aug: *"Avo Maria hasn't traded in far too long / please deep dive"*.
The deep dive took hours and should have taken seconds, because **🙏 avo — the
fleet's real-money directional row — published nothing that could answer it.**
`census = True` appeared exactly ONCE in `lighter_family_bot` (👩 mum v2, a
$1,000 paper book) and the LIVE arm had no census at all: eleven `continue`s
in its entry loop, not one of them counted.

WHAT THE ANSWER WAS, measured by driving the shipped `SwingDip.signals` over
the venue's own 4h tape (23 listed coins, 65 ENTER fires in 15 days):

  * the signal is NOT starved — 119 fires in 30 days;
  * of the 5 fires since the book's last trade, **3 were on coins it already
    holds** (SPY x2, NVDA) and **2 on IWM**, refused by the fail-closed
    per-asset oracle gate because IWM has 172 bars against the oracle's 203
    floor;
  * 24 of 65 fires (37%) land on the three held coins; 12 more on IWM/XCU,
    which cannot be entered at all today.

Held-starved and gate-refused, not signal-starved — and every one of those
refusals was byte-identical to "quiet market" on the row. That is I18, at the
row holding actual money.

These tests pin the instrument, not the verdict:
  1-4  the census cannot invent a reading it does not have (I8);
  5-6  the SHIPPED rule feeds the gauge, and the diagnostics do not move it;
  7    every `continue` in the live entry loop stamps a verdict — so the NEXT
       refusal someone adds cannot be silent, which is the whole class;
  8    the refusal that was actually invisible is counted on the shadow too;
  9    the census survives a restart (a deploy must not blank it);
  10   the loop's defaults block does not clobber the restored census — a real
       defect caught in review of this very change, and the reason the state
       is read ABOVE that block rather than defaulted inside it.
"""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
# NB: no DATABASE_URL here — the root conftest strips it on purpose ((qc)), and
# re-adding it (even empty) reddens `test_db_unreachable_in_tests`. These
# modules import fine without it.

import lighter_avo_live_bot as avo          # noqa: E402
import lighter_family_bot as fam            # noqa: E402

UNI = ["BTC", "ETH", "SPY", "IWM", "XCU"]


def _swingdip():
    return [s for s in fam.STRATEGIES if s.bot == "freqtrade-avo-maria"][0]


# ---- 1-4  the census never invents a reading --------------------------------

def test_the_gauge_is_absent_rather_than_zero_when_nothing_was_read():
    """A fabricated `rsi_min: 0.0` reads as "a coin is AT the bar" — the
    loudest possible signal, from no data at all (I8: unknown never degrades
    to a guess)."""
    out = avo.scan_census({}, {}, 42.0, UNI, [], None, None, 0, None, 1000.0)
    for k in ("rsi_min", "rsi_med", "near_bar", "rsi_read", "rsi_bar"):
        assert k not in out, f"{k} was invented from an empty reading set"


def test_an_unknown_oracle_never_publishes_an_ungraded_LIST():
    """`ungraded=None` means the oracle was not read this cycle (the halt
    paths publish before it is). Listing every non-crypto name off a dark read
    would accuse the gate of refusing books it never saw."""
    dark = avo.scan_census({}, {}, 42.0, UNI, [], None, None, 0, None, 1000.0)
    assert "ungraded" not in dark, "an ungraded list was invented from a dark oracle"
    lit = avo.scan_census({}, {}, 42.0, UNI, [], ["IWM", "XCU"], None,
                          0, None, 1000.0)
    assert lit["ungraded"] == ["IWM", "XCU"]


def test_every_universe_member_gets_a_verdict():
    """A coin the loop never reached must READ as never reached, not vanish —
    a census that silently omits coins understates its own universe."""
    out = avo.scan_census({"BTC": "held"}, {}, 42.0, UNI, ["BTC"], None,
                          None, 0, None, 1000.0)
    assert sum(out["verdicts"].values()) == len(UNI)
    assert out["verdicts"]["not_evaluated"] == len(UNI) - 1
    assert out["universe"] == len(UNI)


def test_idle_clocks_are_absent_rather_than_zero():
    """`idle_open_h: 0.0` would read as "it opened just now" on a book that
    has never opened anything."""
    never = avo.scan_census({}, {}, 42.0, UNI, [], None, None, 0, None, 1000.0)
    assert "idle_open_h" not in never and "idle_close_h" not in never
    some = avo.scan_census({}, {}, 42.0, UNI, [], None, None,
                           1000.0 - 7200.0, 1000.0 - 3600.0, 1000.0)
    assert some["idle_open_h"] == 2.0 and some["idle_close_h"] == 1.0


# ---- 5-6  the shipped rule feeds the gauge, and is not moved by it ----------

def _mild_bars(n=300):
    """A tape that never enters: a steady uptrend, so RSI stays high."""
    c = [100.0 + 0.05 * i + (0.4 if i % 2 else -0.4) for i in range(n)]
    return {"c": c, "h": [x * 1.004 for x in c], "l": [x * 0.996 for x in c],
            "v": [10.0] * n, "t": list(range(n))}


def test_the_gauge_has_a_feeder_and_a_source():
    """Two halves, both required: the carrier must EMIT an rsi on every
    evaluated bar (the NO-ENTRY case is the only one the gauge exists to
    measure), and both loops must CAPTURE it. A gauge nothing writes to is
    the registered-but-inert shape (I18)."""
    s = _swingdip()
    sig = s.signals(_mild_bars(), {})
    assert sig is not None and sig["enter"] is None, "fixture must be no-entry"
    assert isinstance(sig.get("rsi"), (int, float)), (
        "signals() must report its rsi even when it does NOT enter")
    assert s.RSI_MAX == 42.0, "the gauge needs the shipped bar, named"
    live = (ROOT / "lighter_avo_live_bot.py").read_text()
    assert 'last_rsi[sym] = float(sig["rsi"])' in live, "live gauge is inert"
    shadow = (ROOT / "lighter_family_bot.py").read_text()
    assert 'b.last_rsi[coin] = float(sig["rsi"])' in shadow, "shadow gauge is inert"


def test_the_diagnostics_do_not_move_the_entry_decision():
    """The census reads the SHIPPED rule's own numbers ((hj): a second copy of
    a rule is a second rule) — so the rule must still be the rule. `rsi < 42`
    became `rsi < self.RSI_MAX` and RSI_MAX is 42.0: same comparison."""
    s = _swingdip()
    src = (ROOT / "lighter_family_bot.py").read_text()
    tree = ast.parse(src)
    fn = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "SwingDip":
            for sub in node.body:
                if isinstance(sub, ast.FunctionDef) and sub.name == "signals":
                    fn = sub
    assert fn is not None, "SwingDip.signals not found"
    enters = [n for n in ast.walk(fn) if isinstance(n, ast.Assign)
              and any(getattr(t, "id", None) == "enter" for t in n.targets)]
    assert len(enters) == 1, "the entry expression must stay in one place"
    expr = ast.unparse(enters[0].value)
    assert "e50[i] > e200[i]" in expr and "rsi[i] < self.RSI_MAX" in expr \
        and "c[i] < bb_lo" in expr and "v[i] > 0" in expr, expr
    # and it still fires on a real dip
    n = 300
    c = [100.0] * (n - 3) + [92.0, 88.0, 84.0]
    dip = {"c": c, "h": [x * 1.002 for x in c], "l": [x * 0.998 for x in c],
           "v": [10.0] * n, "t": list(range(n))}
    assert s.signals(dip, {}) is not None


# ---- 7  the class: no silent refusal can be added ---------------------------

def test_every_refusal_in_the_live_entry_loop_stamps_a_verdict():
    """THE DURABLE HALF. Counting today's eleven refusals fixes today's
    instance; this fixes the CLASS — a `continue` added to the entry loop
    tomorrow with no `_verdict` beside it fails the build, so the next
    refusal cannot be silent the way `noncrypto_entry_blocked` was."""
    src = (ROOT / "lighter_avo_live_bot.py").read_text()
    tree = ast.parse(src)
    loop = None
    for node in ast.walk(tree):
        if isinstance(node, ast.For) and isinstance(node.iter, ast.Call) \
                and getattr(node.iter.func, "id", None) == "diversified_order":
            loop = node
    assert loop is not None, "the entry loop was renamed — re-aim this test"

    def _nested_loops(n):
        return {x for x in ast.walk(n)
                if isinstance(x, (ast.For, ast.While)) and x is not n}

    inner = _nested_loops(loop)
    exempt = 0
    unstamped = []
    for stmt in ast.walk(loop):
        if not isinstance(stmt, ast.Continue):
            continue
        if any(stmt in ast.walk(i) for i in inner):
            continue                     # belongs to a nested loop, not a refusal
        # find the enclosing `if` body this continue sits in and look for a
        # _verdict(...) call anywhere in that same body
        stamped = False
        for parent in ast.walk(loop):
            for field in ("body", "orelse"):
                body = getattr(parent, field, None)
                if not isinstance(body, list) or stmt not in body:
                    continue
                for sib in body:
                    for call in ast.walk(sib):
                        if isinstance(call, ast.Call) and \
                                getattr(call.func, "id", None) == "_verdict":
                            stamped = True
        if not stamped:
            unstamped.append(getattr(stmt, "lineno", "?"))
    # the ONE legitimate exemption: the same-candle skip is not a refusal, it
    # is "the rule was not evaluated" — stamping it would overwrite the real
    # verdict from the candle that WAS evaluated.
    assert len(unstamped) <= 1, (
        f"unstamped refusals at lines {unstamped} — a silent `continue` in the "
        f"real-money entry loop is exactly the class this census closes")


# ---- 8  the refusal that was actually invisible -----------------------------

def test_the_per_asset_gate_refusal_is_counted_on_both_arms():
    """`noncrypto_entry_blocked` logged and returned with NO counter, so a
    book refused by the fail-closed per-asset gate was byte-identical to a
    book with no signal. Both IWM signals after the drought died here."""
    shadow = (ROOT / "lighter_family_bot.py").read_text()
    i = shadow.index("if noncrypto_entry_blocked(coin, _r_up):")
    assert 'b.scan["noncrypto_ungated"] += 1' in shadow[i:i + 400], \
        "the shadow's per-asset refusal is uncounted again"
    live = (ROOT / "lighter_avo_live_bot.py").read_text()
    j = live.index("if noncrypto_entry_blocked(sym, r_up):")
    assert "_verdict(sym, \"noncrypto_ungated\"" in live[j:j + 700], \
        "the live arm's per-asset refusal is unstamped again"


def test_the_census_distinguishes_a_stale_candle_from_no_signal():
    """Between two 4h closes `sig` is None for every coin, and every coin was
    booked `no_signal` — the I1 liveness trap living INSIDE the instrument
    built to close it."""
    src = (ROOT / "lighter_family_bot.py").read_text()
    assert 'b.scan["stale_candle"] += 1' in src
    i = src.index('b.scan["stale_candle"] += 1')
    # [2026-08-26] the no-signal booking routes through census_no_entry_why
    # (the uptrend_blocked split) — same site, same ordering property.
    j = src.index('b.scan[census_no_entry_why(b.s, sig)] += 1')
    assert i < j, "the stale-candle check must run BEFORE the no-signal count"


# ---- 9-10  it survives a restart, and the defaults do not clobber it --------

def test_the_census_is_persisted():
    """A deploy must not blank the one instrument that says why the book is
    quiet — that would reset it exactly when someone is looking."""
    # [(vm)] BY AST, NOT BY A FIXED-SIZE SOURCE SLICE. This read
    # `src[i:i + 900]` and so depended on how much PROSE sits inside
    # `_persist` — adding a comment explaining why the trend gauge persists
    # pushed `last_open_ts` past the 900th character and failed a test whose
    # subject had not changed. Same class as the two other slice/substring
    # guards corrected today: pin the STRUCTURE the property lives in.
    import ast as _ast
    src = (ROOT / "lighter_avo_live_bot.py").read_text()
    tree = _ast.parse(src)
    fn = next(n for n in _ast.walk(tree)
              if isinstance(n, _ast.FunctionDef) and n.name == "_persist")
    persisted = {}
    for node in _ast.walk(fn):
        if not isinstance(node, _ast.Dict):
            continue
        for k, v in zip(node.keys, node.values):
            if isinstance(k, _ast.Constant) and isinstance(k.value, str):
                persisted[k.value] = _ast.unparse(v)
    # positive control: a walk that finds nothing must not pass vacuously
    assert len(persisted) >= 5, \
        f"_persist parsed to {len(persisted)} keys — the walk is broken"
    for k, expect in (("scan_verdict", "scan_verdict"),
                      ("last_rsi", "last_rsi"),
                      ("last_open_ts", "last_open_ts[0]")):
        assert persisted.get(k) == expect, (
            f"{k} is not persisted as {expect!r} (got {persisted.get(k)!r}) — "
            "a restart blanks the census")


def test_the_loop_defaults_do_not_clobber_the_restored_census():
    """A REAL DEFECT, caught in review of this change. The loop's
    "loop-scope defaults" block runs AFTER the state restore, so adding
    `scan_verdict = {}` there blanks the restored census on EVERY cycle — and
    `closed_win = []` would also blank the window `entries_locked` reads,
    silently unlocking protections. The state must be read above that block
    and never re-defaulted inside it."""
    src = (ROOT / "lighter_avo_live_bot.py").read_text()
    restore_at = src.index("scan_verdict = {str(k): str(v)")
    defaults_at = src.index("# Loop-scope defaults so the publish helper")
    assert restore_at < defaults_at, "restore must precede the defaults block"
    defaults = src[defaults_at:defaults_at + 1400]
    for name in ("scan_verdict", "last_rsi", "last_open_ts", "closed_win"):
        assert f"\n        {name} = " not in defaults and \
               f"\n        {name}, " not in defaults, \
            f"{name} is re-defaulted after the restore — it will be clobbered"
