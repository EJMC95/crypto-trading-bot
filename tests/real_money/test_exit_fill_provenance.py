"""Tier 1 — was the LIVE exit price a measured fill, or the decision mark?

[2026-07-30 (hb)] This finding survived an adversarial verifier that refuted 40
of 44, and it is the one that touches real money.

THE DEFECT. `_real_exit` returns `(px, measured, reason)` and falls back to the
DECISION price on every failure path in `venues/fills.py` — a fallback whose own
docstring calls itself load-bearing. The repo's own measurements say the fallback
is **universal**:

    "0 of 81 live orders ever produced a measured fill"   venues/fills.py
    "0 of 61 real orders ever id-matched"                 venues/lighter_client.py

So `exit_price` on a live close row has been the price the bot DECIDED at, not a
price it OBSERVED — and nothing on the row said so.

WHY THAT IS MORE THAN UNTIDY. `scripts/golive_readiness.py` reads
`fetch_paper_trades`. So do the brain and the promotion judge. None of them can
see a measured flag, because `raw.measured` lives on the `venue_orders` table and
no grading consumer joins it. **The gate that decides whether a book may hold
real money could not distinguish a measured round trip from an assumed one** —
against a gross edge the CHANGELOG puts at +6.18bps/trade, where the verdict
turns entirely on round-trip cost.

SHARPER ON THE TAKER. `lighter_ticket_taker` sets `fee_rate = 0.0` for the live
arm on the stated premise that "its spread is inside the real fill" — the exact
premise `fills.py` measured false. A live row can therefore carry zero fee AND
zero spread.

WHAT THIS CHANGE DOES AND DOES NOT DO. It stamps `exit_measured` /
`exit_fill_src` on the close row. It does **not** touch `fee_rate`, any bar, any
threshold or any decision — deciding what the fee should be has to start from how
many closes were actually measured, and until now that was unknowable from the
graded ledger. Telemetry first, then the argument.
"""
import ast
import pathlib

import pytest

pytestmark = pytest.mark.real_money

_ROOT = pathlib.Path(__file__).resolve().parents[2]
FARMER = (_ROOT / "lighter_funding_bot.py").read_text()
TAKER = (_ROOT / "lighter_ticket_taker.py").read_text()

LIVE = [("lighter_funding_bot", FARMER), ("lighter_ticket_taker", TAKER)]
#: ids, or pytest builds a test id out of the entire ~4,000-line source and a
#: single failure prints 240KB. Learned the hard way on the first run.
LIVE_IDS = [n for n, _ in LIVE]


# --------------------------------------------------------------------------
# 1. The premise: the fallback exists and is silent without this stamp.
# --------------------------------------------------------------------------

def test_the_decision_price_fallback_still_exists():
    """If this ever becomes a hard failure instead of a fallback, the stamp
    stops being necessary and this whole file should be re-read. Asserted so a
    future reader knows which fact the telemetry is compensating for."""
    fills = (_ROOT / "venues/fills.py").read_text()
    assert "def read_fill" in fills or "def _read_fill" in fills
    assert "measured" in fills, "fills.py no longer reports a measured verdict"
    assert "return None" in fills, (
        "read_fill no longer has a None path — if a fill is now always "
        "measured, the decision-price fallback is dead and so is this concern")


def test_the_grading_consumer_reads_the_ledger_not_the_order_table():
    """The reason the stamp has to ride the CLOSE row. If golive_readiness ever
    joins venue_orders, the flag could live there instead."""
    gr = (_ROOT / "scripts/golive_readiness.py").read_text()
    assert "fetch_paper_trades" in gr
    assert "venue_orders" not in gr, (
        "the grader now reads venue_orders — re-check whether the close-row "
        "stamp is still the only path to a measured flag")


# --------------------------------------------------------------------------
# 2. Both live bots stamp it.
# --------------------------------------------------------------------------

@pytest.mark.parametrize("name,src", LIVE, ids=LIVE_IDS)
def test_the_live_book_stamps_whether_its_exit_was_measured(name, src):
    assert "_close_fill_extra(" in src, f"{name} does not stamp fill provenance"
    assert '"exit_measured"' in src, f"{name} omits exit_measured"
    assert '"exit_fill_src"' in src, f"{name} omits exit_fill_src"


@pytest.mark.parametrize("name,src", LIVE, ids=LIVE_IDS)
def test_the_stamp_reaches_the_LEDGER_row_not_only_the_order_row(name, src):
    """The whole point. Both bots already routed measured/fill_reason to the
    venue-order row; no grading consumer joins that table. The flag must be in
    the `extra` of a `publish_paper_trade` call."""
    tree = ast.parse(src)
    stamped = False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        nm = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
        if nm != "publish_paper_trade":
            continue
        for kw in node.keywords:
            if kw.arg != "extra":
                continue
            if "_close_fill_extra" in ast.dump(kw.value):
                stamped = True
    assert stamped, (
        f"{name}: no publish_paper_trade call passes its fill provenance in "
        "extra — the flag would exist only where the graders cannot see it")


@pytest.mark.parametrize("name,src", LIVE, ids=LIVE_IDS)
def test_unknown_is_ABSENT_not_False(name, src):
    """A shadow arm has no venue fill to measure. Recording `False` there would
    claim an unmeasured LIVE fill and quietly poison any later analysis that
    counts unmeasured closes."""
    i = src.index("def _close_fill_extra(")
    body = src[i:i + 3000]
    assert "if measured is not None:" in body, (
        f"{name}: an unknown measured verdict must be omitted, not defaulted")
    assert "setdefault" in body, (
        f"{name}: must not clobber an existing bars/evidence key")


# --------------------------------------------------------------------------
# 3. The Farmer's blind-stop path — the one that used to throw the flags away.
# --------------------------------------------------------------------------

def test_the_blind_stop_path_no_longer_discards_the_flags():
    """It was `_bpx, _, _ = _real_exit(...)`. That path is the fail-safe which
    books a position it could NOT price, so it is the last close whose basis
    should be a mystery."""
    assert "_bpx, _bmeas, _bsrc = _real_exit(" in FARMER, (
        "the blind-stop path discards measured/reason again")
    assert "measured=_bmeas, fill_src=_bsrc" in FARMER, (
        "captured but not passed — the same registered-but-inert shape")


def _close_call_sites(src, fname):
    """(lineno, has_measured_kwarg) for every call to `fname`, by AST.

    NOT by substring. The first version counted `measured=_meas` textually and
    read 5 for 3 sites, because that exact text also appears inside pre-existing
    `_slip_bps_of(..., measured=_meas)` calls — which briefly looked like a
    duplicate-kwarg bug I had introduced into a real-money bot. It was not; the
    count was. A structural claim needs a structural check.
    """
    out = []
    for node in ast.walk(ast.parse(src)):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        nm = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
        if nm == fname:
            out.append((node.lineno, "measured" in {k.arg for k in node.keywords}))
    return out


def test_every_farmer_close_site_passes_its_provenance():
    """All three. One unstamped site is a silent hole exactly where the others
    look covered."""
    sites = _close_call_sites(FARMER, "_record_close")
    assert len(sites) >= 3, f"expected >=3 close sites, found {len(sites)}"
    missing = [ln for ln, ok in sites if not ok]
    assert not missing, f"Farmer close sites without provenance: lines {missing}"


def test_every_taker_close_site_passes_its_provenance():
    """`_book_close` takes measured/fill_reason as parameters, so every call
    must supply them — a defaulted None reverts to the old inference."""
    sites = _close_call_sites(TAKER, "_book_close")
    assert len(sites) >= 2, f"expected >=2 close sites, found {len(sites)}"


# --------------------------------------------------------------------------
# 4. Nothing that decides anything changed. This is the safety claim.
# --------------------------------------------------------------------------

def test_the_takers_fee_rate_premise_is_untouched_and_still_recorded():
    """DELIBERATELY NOT FIXED HERE. The live arm's `fee_rate = 0.0` rests on
    "its spread is inside the real fill", which fills.py measured false — but
    changing a fee changes recorded P&L on a real-money book, and the right
    order is to make the premise checkable first. This test pins that the
    premise is still there to be argued about, so the telemetry cannot be
    mistaken for having resolved it."""
    assert "fee_rate" in TAKER
    assert "_close_fill_extra(" in TAKER, (
        "the telemetry that would let anyone check the premise is gone")


@pytest.mark.parametrize("name,src", LIVE, ids=LIVE_IDS)
def test_no_exit_threshold_moved(name, src):
    """The claim that makes this shippable to real money without a backtest.
    Every exit constant must still read from its env with its known default."""
    for var, default in (("FUNDING_TAKE_PROFIT", "0.04"),
                         ("FUNDING_HARD_STOP", "0.10"),
                         ("FUNDING_MAX_HOLD_H", "72"),
                         ("TT_TP", "0.04"), ("TT_SL", "-0.03"),
                         ("TT_MAX_HOLD_H", "48")):
        if f'"{var}"' in src:
            assert f'"{var}", "{default}"' in src, (
                f"{name}: {var} default moved — this change was supposed to be "
                "telemetry only")
