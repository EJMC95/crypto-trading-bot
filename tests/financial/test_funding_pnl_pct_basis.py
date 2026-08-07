"""[(lj)] A funding book's `pnl_pct` must be the same return as its `pnl_abs`.

THE DEFECT. ⚖️ Counterweight wrote

    pnl_abs = price_pnl + accrued          # the real return
    pnl_pct = (exit_px - ent_px) / ent_px  # PRICE ONLY

— two fields, two different definitions of what the trade returned. And the
go-live grader reads **both**: `mean` and `t` come from `pnl_pct`
(`stats`: `pct = [r[0] for r in rows]`), while `halves` and `maxdd` come from
`pnl_abs` (`h1 = sum(r[1] ...)`, `eq += r[1]`).

On this book that split is the worst possible one. Counterweight is
DELTA-NEUTRAL by construction — long K, short K, dollar-balanced — so its price
return is noise around zero BY DESIGN and funding on both legs is the entire
thesis. **The two bars that decide statistical significance were measuring the
one component the book does not trade**, while the drawdown bars measured the
right one. Every recorded expectancy figure for it, including the `(hc)` note's
"mean +1.263% / win 68%", is on the price-only basis.

CONTROL GROUP (I6) — an absence is evidence only against a population where the
thing is present. All three sibling funding books already denominate on the
deployed clip, so Counterweight was the lone outlier and this is a defect rather
than a house convention:

    funding_carry_bot.py        pnl_pct = pnl / pos["notional"]
    lighter_band_barnes_bot.py  pnl_pct = pnl / pos["notional"]
    lighter_funding_bot.py      pnl_pct = pnl / order_usd
                                ("pnl_abs = price P&L + funding accrued;
                                  pnl_pct is on the deployed clip")

This is an ACCOUNTING-BASIS change, which is the declared era-reset condition,
so `POLICY_ERA` and `bot_learn.ERA_START` both move to 2026-08-07 in lockstep —
the gate's sample may never be wider than the brain's.
"""
import ast
import pathlib

import pytest

pytestmark = [pytest.mark.financial, pytest.mark.autonomy]

ROOT = pathlib.Path(__file__).resolve().parents[2]

import lighter_funding_spread_bot as FS        # noqa: E402
import scripts.golive_readiness as GR          # noqa: E402
import bot_learn as BL                         # noqa: E402


class _Rec:
    """Captures the row the book hands to publish_paper_trade."""

    def __init__(self):
        self.rows = []

    def publish_paper_trade(self, bot, **kw):
        self.rows.append(kw)


@pytest.fixture
def rec(monkeypatch):
    r = _Rec()
    monkeypatch.setattr(FS.store, "publish_paper_trade", r.publish_paper_trade)
    return r


# ---------------------------------------------------------------------------
# the basis
# ---------------------------------------------------------------------------

def test_pnl_pct_is_the_total_return_on_the_deployed_clip(rec):
    """A delta-neutral leg: price moves nothing, funding earns $3 on a $200
    clip. The old basis reported 0.0%; the truth is +1.5%."""
    FS._record_close("perps-funding-spread-lshadow", "BTC",
                     ent_px=100.0, ent_ts=1_800_000_000, exit_px=100.0,
                     total_pnl=3.0, was_long=True, reason="rebalance",
                     shadow=None, notional=200.0)
    row = rec.rows[-1]
    assert row["pnl_abs"] == pytest.approx(3.0)
    assert row["pnl_pct"] == pytest.approx(3.0 / 200.0), (
        "pnl_pct is not the total return on the clip — a delta-neutral funding "
        f"leg reported {row['pnl_pct']}")


def test_the_two_fields_agree_about_the_sign(rec):
    """The sharpest form of the bug: a leg whose PRICE went the right way while
    the trade LOST money overall. The old basis published a positive percentage
    and a negative dollar figure for the same trade, so `mean` and `halves`
    disagreed about whether it was a win."""
    FS._record_close("perps-funding-spread-lshadow", "ETH",
                     ent_px=100.0, ent_ts=1_800_000_000, exit_px=102.0,
                     total_pnl=-5.0, was_long=True, reason="rebalance",
                     shadow=None, notional=200.0)
    row = rec.rows[-1]
    assert row["pnl_abs"] < 0
    assert row["pnl_pct"] < 0, (
        f"pnl_abs={row['pnl_abs']} but pnl_pct={row['pnl_pct']} — the grader's "
        "mean/t bars and its halves/maxdd bars would disagree about the sign "
        "of the same trade")


def test_a_short_leg_is_denominated_the_same_way(rec):
    FS._record_close("perps-funding-spread-lshadow", "SOL",
                     ent_px=100.0, ent_ts=1_800_000_000, exit_px=98.0,
                     total_pnl=4.0, was_long=False, reason="rebalance",
                     shadow=None, notional=200.0)
    assert rec.rows[-1]["pnl_pct"] == pytest.approx(4.0 / 200.0)


def test_a_pre_fix_position_still_publishes_a_percentage(rec):
    """Fail-safe. A position restored from state written before this change has
    no `notional`; emitting None would DROP the row from the grader's sample
    entirely (`stats` filters on `isinstance(r[0], (int, float))`), which is a
    worse outcome than one row on the old basis."""
    FS._record_close("perps-funding-spread-lshadow", "BTC",
                     ent_px=100.0, ent_ts=1_800_000_000, exit_px=101.0,
                     total_pnl=3.0, was_long=True, reason="rebalance",
                     shadow=None, notional=None)
    assert rec.rows[-1]["pnl_pct"] == pytest.approx(0.01)


def test_a_zero_notional_does_not_divide_by_zero(rec):
    FS._record_close("perps-funding-spread-lshadow", "BTC",
                     ent_px=100.0, ent_ts=1_800_000_000, exit_px=101.0,
                     total_pnl=3.0, was_long=True, reason="rebalance",
                     shadow=None, notional=0.0)
    assert rec.rows[-1]["pnl_pct"] == pytest.approx(0.01)


def test_the_notional_is_captured_at_open():
    """Reading `order_usd` at CLOSE would misattribute every trade whose clip
    the growth rail moved mid-life."""
    src = pathlib.Path(FS.__file__).read_text()
    tree = ast.parse(src)
    found = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            keys = [k.value for k in node.keys
                    if isinstance(k, ast.Constant)]
            if "is_short" in keys and "accrued" in keys:
                assert "notional" in keys, (
                    "the position meta written at open does not record the "
                    f"leg's notional: {keys}")
                found = True
    assert found, "could not find the position-meta literal — scan is blind"


def test_the_close_path_forwards_the_notional():
    """Wiring, and it is a separate failure from the two above.

    `_record_close` can be perfectly correct and the meta can carry the
    notional, while the CALL between them drops it — in which case every real
    close silently falls back to the price-only basis and the direct-call tests
    above stay green. `close_position` is a closure inside `main()`, so this is
    asserted on the call rather than by driving it: the claim is a
    RELATIONSHIP (the call must forward the field from the position meta), not
    that a name appears somewhere.
    """
    tree = ast.parse(pathlib.Path(FS.__file__).read_text())
    # Scope past `_selftest`, whose own calls are positional fixtures rather
    # than production wiring — counting them would make this assert a
    # convention the selftest does not follow.
    skip = set()
    for fn in ast.walk(tree):
        if isinstance(fn, ast.FunctionDef) and "selftest" in fn.name:
            skip.update(range(fn.lineno, (fn.end_lineno or fn.lineno) + 1))
    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == "_record_close" and n.lineno not in skip]
    assert calls, "no production _record_close call site found — scan is blind"
    for c in calls:
        kw = {k.arg: ast.unparse(k.value) for k in c.keywords if k.arg}
        assert "notional" in kw, (
            f"line {c.lineno}: _record_close is called without `notional`, so "
            "this close falls back to the price-only basis")
        assert "notional" in kw["notional"], (
            f"line {c.lineno}: `notional` is not taken from the position meta: "
            f"{kw['notional']!r}")


# ---------------------------------------------------------------------------
# the control group, asserted rather than described
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("mod", ["funding_carry_bot.py",
                                 "lighter_band_barnes_bot.py",
                                 "lighter_funding_bot.py"])
def test_every_sibling_funding_book_denominates_on_the_clip(mod):
    """If a sibling ever moves to a price-only percentage, this book's basis is
    no longer the fleet's and the comparison in the changelog stops holding."""
    src = (ROOT / mod).read_text()
    assert ("pnl_pct=pnl / pos[\"notional\"]" in src
            or "pnl_pct = (pnl / (order_usd or 1.0))" in src
            or "pnl_pct=pnl_pct" in src), (
        f"{mod} no longer denominates pnl_pct on the deployed clip")
    assert "(exit_px - ent_px) / ent_px" not in src, (
        f"{mod} has grown a price-only pnl_pct")


# ---------------------------------------------------------------------------
# the era moved, and it moved in BOTH tables
# ---------------------------------------------------------------------------

def test_the_era_reset_and_the_two_tables_agree():
    """An accounting-basis fix is the declared reset condition, and 'the gate's
    sample may never be wider than the brain's'."""
    gate = GR.POLICY_ERA["perps-funding-spread"][0]
    brain = BL.ERA_START["perps-funding-spread"]
    # DERIVED, not hardcoded: `audit_era_date_literals` owns these dates, and a
    # legitimate table move must not redden a test that is not about the date.
    # The invariant here is AGREEMENT — "the gate's sample may never be wider
    # than the brain's" — which is also what catches either table being left
    # behind, so no literal is needed to detect the regression.
    assert brain.startswith(gate), (
        f"gate era {gate} and brain era {brain} disagree — the grader would "
        "grade a sample the brain does not")
    # NO "and it moved to <date>" assertion, deliberately. Both regressions
    # this test exists for — either table left behind — break AGREEMENT, so a
    # literal adds nothing and would itself be a hardcoded canonical date. That
    # the era moved FOR THIS REASON is asserted by the reason test below.


def test_the_era_reason_preserves_the_earlier_one():
    """An era is the LATEST of every invalidating change; moving the date
    forward must preserve the earlier reason rather than discard it."""
    why = GR.POLICY_ERA["perps-funding-spread"][1]
    assert "17-Jul" in why and "accrual" in why, why
    assert "PRICE-ONLY" in why or "price-only" in why, why
