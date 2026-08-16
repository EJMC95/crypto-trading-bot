"""[2026-08-16 (nl)] A FUNDING BOOK AT CAP PUBLISHED NOTHING ABOUT WHAT IT WAS
TURNING AWAY.

THE INCIDENT. `lighter_funding_bot.py`'s entry prefilter lives inside
`if open_now < max_open`, so a book at its position limit **does not scan at
all**. The row then publishes `held: {…}` and `hottest_apr` (the VENUE's
hottest, not the band's) and nothing else — and `{6 held}` is byte-identical
between *"holding the best six the venue offers"* and *"the four highest-APR
coins in this band are turned away every loop"*. That is I18 verbatim: a book
that cannot open must publish its own census at its own bar, because the
open-count cannot tell quiet from structurally impossible. 🎸 Barnes was given
exactly this instrument at `(lv)` after its `extreme` sleeve ran dead for 8 days
behind an indistinguishable payload.

THE MEASUREMENT (16-Aug): 🛢️ Garrett sat at **6 of 6** on a band holding **26
qualifying coins** and held **none of the four highest-APR** ones (KAITO 205%,
ROBO 124%, APT 46%, ETHFI 24.5%) — it held four coins at ~10.5%. That may be
entirely correct (those four are $0.13–0.42M books; the spread/slip vetoes
plausibly reject them, and positions opened when the ranking differed) but
nothing published could say which — and Garrett is the fleet's fastest path to a
graded book (2.09 closes/day, n=30 ~27-Aug).

WHY THIS FILE IS MOSTLY ABOUT WHAT DID **NOT** CHANGE. This module runs 💸 the
LIVE Funding Farmer as well as 🛢️ Garrett, so the census must be provably
read-only: it opens nothing, is consulted by no entry decision, and the trading
path is byte-identical with or without it. Publish-only ⇒ main-only under
`(mm)`; it rides the next deploy that actually changes a trade.

MUTATION-VERIFIED — each of these reddens this file:
  1. `capped` reported as `eligible` even when free slots remain
  2. the persistence bucket counted as `eligible`
  3. `is_crypto` used to SKIP a coin instead of merely counting it
  4. `top` sorted by signed apr instead of |apr|
  5. the census call moved inside the `open_now < max_open` branch
"""
import ast
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

MODULE = os.path.join(ROOT, "lighter_funding_bot.py")
H = 3.0 * 365.0


@pytest.fixture(scope="module")
def bot():
    return pytest.importorskip("lighter_funding_bot")


def _fund():
    return {
        "KAITO": {"rate": 2.05 / H, "vol": 0.42e6},
        "ROBO": {"rate": 1.24 / H, "vol": 1.53e6},
        "APT": {"rate": 0.46 / H, "vol": 0.14e6},
        "BNB": {"rate": 0.105 / H, "vol": 1.19e6},
        "TINY": {"rate": 0.01 / H, "vol": 0.5e6},     # below the apr gate
        "BTC": {"rate": 0.50 / H, "vol": 207e6},      # above the band
        "XMR": {"rate": 0.105 / H, "vol": 0.34e6},    # held
    }


def _kw(**over):
    base = dict(cooldown={}, t0=1e6, hot_since={}, enter_gate=0.05,
                min_vol=1e5, max_vol=2e6, persist_h=0.0, h_per_year=H)
    base.update(over)
    return base


# ------------------------------------------------ the number that was missing
def test_at_cap_the_census_still_reports_what_is_turned_away(bot):
    """The whole point: AT CAP the real prefilter never runs."""
    c = bot.scan_census(_fund(), held={"XMR"}, max_open=6, open_now=6, **_kw())
    assert c["free_slots"] == 0
    assert c["eligible"] == 4
    assert c["capped"] == 4, (
        "four qualified candidates with no slot — the quantity `held: {6}` "
        "could never express, and the reason a dead book and a full one "
        "published the same payload")
    assert [t["sym"] for t in c["top"]][:3] == ["KAITO", "ROBO", "APT"]


def test_capped_is_zero_while_slots_remain(bot):
    """`capped` must mean *blocked by the cap*, not *eligible*.

    Conflating them would make every healthy loop look capacity-starved and
    train the operator to ignore the field — the (gl) overstating-detector trap
    this instrument exists to avoid.
    """
    c = bot.scan_census(_fund(), held={"XMR"}, max_open=6, open_now=2, **_kw())
    assert c["eligible"] == 4 and c["free_slots"] == 4 and c["capped"] == 0


def test_top_ranks_by_absolute_apr(bot):
    """A funding book takes the receiving side of either sign, so the ranking
    that matters is |apr| — sorting signed would bury the hottest shorts."""
    f = {"POS": {"rate": 0.30 / H, "vol": 1e6},
         "NEG": {"rate": -2.00 / H, "vol": 1e6}}
    c = bot.scan_census(f, held=set(), max_open=6, open_now=0, **_kw())
    assert [t["sym"] for t in c["top"]] == ["NEG", "POS"]


# ------------------------------------------------------------ bucket meanings
def test_persistence_is_waiting_not_eligible(bot):
    c = bot.scan_census(_fund(), held=set(), max_open=6, open_now=0,
                        **_kw(persist_h=6.0,
                              hot_since={k: 1e6 for k in _fund()}))
    assert c["waiting"] == 5 and c["eligible"] == 0


def test_the_class_screen_is_reported_never_applied(bot):
    """This module has NO `_class_ok` while its three sibling funding books do.

    That asymmetry was measured on 16-Aug and the change was **refused**: the
    live arm's non-crypto sample reads n=12, −$1.17, t=−0.44 while the shadow
    arm reads n=22, **+$1.78**, t=+0.29 — the arms disagree in sign and neither
    is significant, so screening real money on it would be a veto firing on
    noise (I15/I19). Counting keeps the question answerable as n grows; if this
    ever starts SKIPPING, a refused change has been shipped by the back door.
    """
    c = bot.scan_census(_fund(), held=set(), max_open=6, open_now=0,
                        is_crypto=lambda s: s != "APT", **_kw())
    assert c["noncrypto"] == 1
    assert c["eligible"] == 5, "counted, and STILL eligible"


def test_a_raising_is_crypto_cannot_break_the_census(bot):
    def boom(_s):
        raise RuntimeError("bus dark")
    c = bot.scan_census(_fund(), held=set(), max_open=6, open_now=0,
                        is_crypto=boom, **_kw())
    assert c["eligible"] == 5


@pytest.mark.parametrize("bad", [{}, None])
def test_degenerate_input_never_raises(bot, bad):
    """This runs inside the publish path of a real-money book."""
    c = bot.scan_census(bad, held=set(), max_open=6, open_now=0, **_kw())
    assert c["scanned"] == 0 and c["eligible"] == 0 and c["top"] == []


def test_unbounded_band_is_supported(bot):
    """💸 the Farmer has a floor and no ceiling; 🛢️ Garrett has both."""
    c = bot.scan_census(_fund(), held=set(), max_open=6, open_now=0,
                        **_kw(min_vol=1e7, max_vol=None))
    assert c["eligible"] == 1 and c["band_usd"][1] is None


def test_the_band_and_gate_are_published_not_just_the_floor(bot):
    """(gl)'s corollary, engraved in I20: publish the BAND, not just the floor.

    An unpublished ceiling made 🛢️ Garrett read as a rival for supply its own
    band excludes. A census that states `gate_apr` and both band edges can be
    checked against the venue by anyone.
    """
    c = bot.scan_census(_fund(), held=set(), max_open=6, open_now=0, **_kw())
    assert c["band_usd"] == [1e5, 2e6] and c["gate_apr"] == 0.05


# ------------------------------------- what must NOT have changed (live money)
def test_scan_census_is_read_only():
    """It must not open, close, order, or write state. AST, not substring.

    This module places REAL orders. A census that could act is not a census.
    """
    with open(MODULE, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=MODULE)
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == "scan_census"),
              None)
    assert fn is not None, "scan_census not found"

    banned = {"_open_position", "market_open", "place_order", "_close",
              "save_state", "publish", "write_levers", "close_position"}
    called = {n.func.id for n in ast.walk(fn)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    called |= {n.func.attr for n in ast.walk(fn)
               if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    leaked = banned & called
    assert not leaked, f"scan_census must be read-only; it calls {sorted(leaked)}"


def test_the_entry_decision_does_not_consult_the_census():
    """The trading path must be byte-identical with or without this feature.

    If any entry/skip branch ever reads the census, a reporting instrument has
    silently become an actuator — the failure `(fz)`-era levers kept producing.
    """
    with open(MODULE, encoding="utf-8") as fh:
        src = fh.read()
    tree = ast.parse(src, filename=MODULE)
    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == "scan_census"]
    assert calls, "the census is never called — registered-but-inert"
    # every call site must be a value going into the published payload, never
    # a test/condition: no call may appear inside an `if`/`while` test.
    for node in ast.walk(tree):
        if isinstance(node, (ast.If, ast.While)):
            for sub in ast.walk(node.test):
                assert not (isinstance(sub, ast.Call)
                            and isinstance(sub.func, ast.Name)
                            and sub.func.id == "scan_census"), (
                    "scan_census appears in a control-flow TEST — the census "
                    "must never gate a trading decision")


def test_the_census_is_published_outside_the_cap_branch():
    """Publishing it inside `if open_now < max_open` would reproduce the bug.

    The entire finding is that a book AT CAP publishes nothing about what it is
    refusing; a census that only runs when there is room says nothing in exactly
    the state that needed explaining.
    """
    with open(MODULE, encoding="utf-8") as fh:
        src = fh.read()
    tree = ast.parse(src, filename=MODULE)

    def _guards_on_cap(test):
        return any(isinstance(s, ast.Name) and s.id in ("max_open", "open_now")
                   for s in ast.walk(test))

    for node in ast.walk(tree):
        if isinstance(node, ast.If) and _guards_on_cap(node.test):
            for sub in ast.walk(node):
                if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name)
                        and sub.func.id == "scan_census"):
                    raise AssertionError(
                        "scan_census is called inside a branch guarded by the "
                        "position cap — it must publish AT cap, which is the "
                        "whole reason it exists")


def test_module_selftest_passes():
    r = subprocess.run([sys.executable, MODULE, "--selftest"],
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, f"{r.stdout}\n{r.stderr}"
    assert "_selftest_scan_census OK" in r.stdout
