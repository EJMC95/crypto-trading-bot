"""Halt events reach the brain (which sizes real money) and the judge (which
promotes to it).

[2026-08-28 (vd)] A $0.00 close with no entry price is a halt/flatten EVENT.
`golive_readiness` has excluded them since (th); `fleet_allocation` joined
earlier today. These two are the ones that ACT:

  * `bot_learn._fetch_trades` — every living book reads this brain through
    `fleet_bus.brain_clip`, clamped [1/6.7, 6.7], and that includes the three
    live real-money rows. MEASURED: 🙏 avo's card read **n=15, wins=5, 33.3%**
    where her true record is **n=6, wins=5, 83.3%** — a 50pp error on a live
    book. A phantom is FREE `n` carrying no information, and nearly every bar
    in `qualify_v3` is size-driven, so rows that say nothing satisfy them
    faster.

  * `experiment_judge.arm_trades` — the sample the PROMOTION decision is made
    on. Its own published power block already excluded them; the deciding path
    did not.

EXPECTANCY TODAY IS ZERO ON BOTH, verified rather than assumed — the three
books carrying brain multipliers (book-douglas, perps-funding-carry,
lighter-ticket-taker) have no phantom rows, and every judged pair is
`unjudgeable` or `stood_down`. Shipped as correctness.

THE PREDICATE'S OWN CONTRACT is pinned here too, because widening it to accept
both ledger shapes broke it once in the dangerous direction and the judge's
`--selftest` is what caught it.
"""
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from golive_readiness import is_phantom_close                # noqa: E402


def _clean(body):
    """Run in a CLEAN interpreter from the repo root — pytest puts `scripts/`
    on sys.path, so an in-process check answers the question the code is
    supposed to answer."""
    return subprocess.run([sys.executable, "-c", body], cwd=str(ROOT),
                          capture_output=True, text=True, timeout=300)


# --------------------------------------------------------- the contract
@pytest.mark.parametrize("row,expected,why", [
    ({}, False, "no keys at all must fail OPEN"),
    ({"profit_ratio": 0.0, "close_ts": "x"}, False,
     "a row with neither price shape must fail OPEN — this exact case "
     "collapsed the judge's paired bar to n=0 when the widening first shipped"),
    ({"profit_abs": 0.0, "open_rate": None}, True, "DB-shape phantom"),
    ({"pnl_abs": 0.0, "entry_price": None}, True, "/trades.json-shape phantom"),
    ({"profit_abs": -3.87, "open_rate": 0.31}, False, "DB-shape real close"),
    ({"pnl_abs": -3.87, "entry_price": 0.31}, False, "feed-shape real close"),
    ({"profit_abs": -1.2, "open_rate": None}, False,
     "a REAL loss whose fill price is merely absent is not a phantom"),
    ({"profit_abs": "junk", "open_rate": None}, False, "unparseable"),
])
def test_the_phantom_contract(row, expected, why):
    assert is_phantom_close(row) is expected, why


def test_it_can_never_silently_shrink_a_sample():
    """THE FAIL-OPEN DIRECTION, which the widening violated once.

    A filter that can drop rows it does not understand is strictly worse than
    one that misses a few events — it shrinks a GRADED sample, and the graders
    downstream govern real money. So: a row must POSITIVELY carry one of the
    two shapes to be judged a phantom at all.
    """
    for row in ({}, {"foo": 1}, {"profit_ratio": 0.0}, {"close_ts": "x"},
                {"bot": "b", "reason": "long_daily_loss"}):
        assert is_phantom_close(row) is False, (
            f"{row} carries no P&L shape and must not be droppable")


def test_both_shapes_agree_on_the_live_ledger():
    """The two shapes are the same rows, or one of the consumers is wrong."""
    import json
    import urllib.request
    url = ("https://pnl-dashboard-production-858c.up.railway.app"
           "/trades.json?source=paper&limit=9000")
    try:
        rows = json.load(urllib.request.urlopen(url, timeout=90))["trades"]
    except Exception as exc:                                 # noqa: BLE001
        pytest.skip(f"live feed unavailable: {exc}")

    def to_db(r):
        d = {k: v for k, v in r.items() if k not in ("pnl_abs", "entry_price")}
        d["profit_abs"] = float(r.get("pnl_abs") or 0.0)
        d["open_rate"] = r.get("entry_price")
        return d

    feed = {r["trade_id"] for r in rows if is_phantom_close(r)}
    db = {r["trade_id"] for r in map(to_db, rows) if is_phantom_close(r)}
    assert feed == db, f"shapes disagree on {len(feed ^ db)} rows"
    assert feed, "no phantoms in the feed — this check would be vacuous"


# --------------------------------------------------------- the two actuators
def test_the_brain_drops_halt_events_from_a_clean_interpreter():
    """Drive the REAL `_fetch_trades`. The `sys.path` insert it needs is the
    same one whose absence made `fleet_allocation`'s filter inert in production
    for a whole deploy — an import inside a swallowing `except` is a silent
    kill switch."""
    r = _clean(
        "import sys, types\n"
        "PH = {'bot':'x','profit_abs':0.0,'open_rate':None,'pnl_pct':0.0,\n"
        "      'is_open':False,'reason':'long_daily_loss'}\n"
        "REAL = {'bot':'x','profit_abs':-1.2,'open_rate':0.31,'pnl_pct':-0.004,\n"
        "        'is_open':False,'reason':'long_stop_loss'}\n"
        "m = types.ModuleType('bot_pnl_store')\n"
        "m.fetch_paper_trades = lambda limit=None: "
        "[dict(REAL) for _ in range(5)] + [dict(PH) for _ in range(4)]\n"
        "sys.modules['bot_pnl_store'] = m\n"
        "import bot_learn\n"
        "out = bot_learn._fetch_trades()\n"
        "left = sum(1 for t in out if t.get('open_rate') is None "
        "and float(t.get('profit_abs') or 0) == 0.0)\n"
        "print('PHANTOMS_LEFT', left)\n")
    assert "PHANTOMS_LEFT 0" in r.stdout, (
        f"the brain still ingests halt events:\n{r.stdout}\n{r.stderr}")


def test_the_judge_drops_halt_events_from_a_clean_interpreter():
    r = _clean(
        "import experiment_judge as ej\n"
        "PH = {'bot':'b','profit_ratio':0.0,'profit_abs':0.0,'open_rate':None,\n"
        "      'close_ts':'2026-08-27T10:00:00Z','reason':'long_daily_loss'}\n"
        "REAL = {'bot':'b','profit_ratio':-0.004,'profit_abs':-1.2,\n"
        "        'open_rate':0.31,'close_ts':'2026-08-27T11:00:00Z',\n"
        "        'reason':'long_stop_loss'}\n"
        "rows = [dict(REAL) for _ in range(5)] + [dict(PH) for _ in range(4)]\n"
        "print('KEPT', len(ej.arm_trades(rows, 'b', 0, 4102444800)))\n")
    assert "KEPT 5" in r.stdout, (
        f"the promotion sample still counts halt events:\n{r.stdout}\n{r.stderr}")


def test_the_judge_does_NOT_apply_strip_exits_here():
    """THE REFUSAL, pinned so a future pass does not 'complete' the fix.

    The pair specs declare `strip_exits = (daily_loss, kill_switch,
    v1_legacy)`, and a sweep recommended applying them in `arm_trades` too.
    Refused, with the number: on 🔮 georgia's LIVE arm, phantom-filtering alone
    gives n=57 at -0.1768%/trade; adding `strip_exits` gives n=51 at
    **+0.0535%/trade**. It FLIPS A LOSING REAL-MONEY ARM POSITIVE by discarding
    six trades that cost real dollars.

    Whether a forced flatten belongs in a promotion sample is a real policy
    question with a measured sign change attached. It is not a correctness fix
    and must not ride in on one.
    """
    import ast
    src = (ROOT / "experiment_judge.py").read_text()
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == "arm_trades")
    body = ast.get_source_segment(src, fn) or ""
    # the docstring may DISCUSS strip_exits; the code must not apply it
    code = body.split('"""')[-1]
    assert "strip_exits" not in code, (
        "arm_trades now applies strip_exits — that removes REAL losses and "
        "flips georgia's live mean positive. If this is intended it needs its "
        "own measurement and its own entry, not this test deleted.")


def test_the_brain_actually_reaches_real_money():
    """A fix nobody consumes is not worth shipping — this ties the brain change
    to the claim that it touches real money."""
    src = (ROOT / "fleet_bus.py").read_text()
    assert "def brain_clip" in src
    assert "MULT_CEIL" in src and "MULT_FLOOR" in src


# ------------------------------------------- the brain publishes its own receipt
def test_the_brain_publishes_how_many_events_it_dropped():
    """[2026-08-28 (vd)] VERIFYING THE BRAIN FIX FROM OUTSIDE WAS IMPOSSIBLE,
    and that is why this exists.

    The brain publishes `runs`, `vitals`, `venue_ab`, `diagnoses`, `hypotheses`
    and `mult_streaks` — not one carries a per-book sample size. So a run that
    excluded 13 halt events and a run whose import failed and excluded ZERO
    produced byte-identical payloads. A monitor armed on this organ could only
    ever time out, which is precisely what happened.

    `fleet_allocation` publishes `n_phantom` for the same reason. This is that
    receipt one organ over: 0 = ran and found none, None = could not run.
    """
    src = (ROOT / "bot_learn.py").read_text()
    assert '"phantom_excluded": _PHANTOM_EXCLUDED' in src, (
        "the brain drops halt events but publishes no receipt saying so")
    assert "_PHANTOM_EXCLUDED = None" in src, (
        "the receipt must START as None — a 0 default would claim the filter "
        "ran clean on a run where it never ran at all")

    r = _clean(
        "import sys, types\n"
        "PH = {'bot':'x','profit_abs':0.0,'open_rate':None,'pnl_pct':0.0,\n"
        "      'is_open':False,'reason':'long_daily_loss'}\n"
        "REAL = {'bot':'x','profit_abs':-1.2,'open_rate':0.31,'pnl_pct':-0.004,\n"
        "        'is_open':False,'reason':'long_stop_loss'}\n"
        "m = types.ModuleType('bot_pnl_store')\n"
        "m.fetch_paper_trades = lambda limit=None: "
        "[dict(REAL) for _ in range(5)] + [dict(PH) for _ in range(4)]\n"
        "sys.modules['bot_pnl_store'] = m\n"
        "import bot_learn\n"
        "assert bot_learn._PHANTOM_EXCLUDED is None\n"
        "bot_learn._fetch_trades()\n"
        "print('RECEIPT', bot_learn._PHANTOM_EXCLUDED)\n")
    assert "RECEIPT 4" in r.stdout, (
        f"the receipt did not count the 4 halt events:\n{r.stdout}\n{r.stderr}")


def test_zero_and_none_are_distinguishable_on_the_receipt():
    """The whole point of the receipt. If the fail path set 0 the payload could
    not tell 'clean sample' from 'filter never ran' — which is the ambiguity
    that let a dead filter sit live in `fleet_allocation` for a whole deploy."""
    import ast
    src = (ROOT / "bot_learn.py").read_text()
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == "_fetch_trades")
    handlers = [h for n in ast.walk(fn) if isinstance(n, ast.Try)
                for h in n.handlers]
    assigns_none = any(
        isinstance(s, ast.Assign)
        and any(getattr(t, "id", "") == "_PHANTOM_EXCLUDED" for t in s.targets)
        and isinstance(s.value, ast.Constant) and s.value.value is None
        for h in handlers for s in ast.walk(h))
    assert assigns_none, (
        "the fail-open path must set _PHANTOM_EXCLUDED = None, never 0")
