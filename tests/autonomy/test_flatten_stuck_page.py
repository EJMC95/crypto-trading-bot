"""[2026-09-03 (xr)] A HALTED BOOK WHOSE FLATTEN NEVER COMPLETES MUST PAGE.

`(xo)` fixed the INSTANCE — a 1000-market that `market_close` could not look
up, so 👩 mum's daily-loss halt retried for 6.9 hours against $442 of a $524
real-money book and never closed it. This closes the CLASS.

THE MEASUREMENT THAT MOTIVATES IT, and it is the whole argument: at the moment
of the incident `extra.flatten_incomplete` was published by BOTH
real-money-capable hosts (`lighter_avo_live_bot`, `lighter_ticket_taker`) and
consumed by NOTHING — no detector, no page, no dashboard chip. Grep on
origin/main the morning after returned two publishers, one docstring and one
comment. The condition was fully observable and nobody was looking, which is
why it ran for 6.9h and was found by a human reading a P&L brief.

A flatten can fail for reasons `(xo)` does not touch — a venue error, an empty
book, a rejected reduce-only, the next spelling nobody has met. Every one is
byte-identical from outside: `status: halted`, a quiet row, a position still
on. That is I1/I18's shape, and I13's argument for an OUT-OF-PROCESS check:
the in-process retry is behaving exactly as designed, and its log line reads
like safety ("not booking a phantom close" — correct, and it is the sentence
that made 6.9 hours look fine).

Every fixture below carries mum's real published shape.
"""
import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import fleet_immune as fi   # noqa: E402

NOW = 1_756_800_000.0

#: mum's row as published during the (xo) incident, field-for-field.
def _mum(flat=True, age=60, open_n=1, svc="mum-live"):
    return {
        "bot": "freqtrade-mum-lighter",
        "status": "halted",
        "equity": 523.82,
        "open_trades": open_n,
        "age_sec": age,
        "extra": {
            "svc": svc,
            "halted": True,
            "day": "2026-09-02",
            "held": {"1000PEPE": "adopted"},
            **({"flatten_incomplete": flat} if flat is not None else {}),
        },
    }


def _healthy(bot="freqtrade-avo-maria-lighter"):
    """A live book that is NOT halted — the control group. A detector that
    flags everything trains the operator to ignore it ((hh))."""
    return {"bot": bot, "status": "online", "open_trades": 5, "age_sec": 30,
            "extra": {"svc": "tide-rider-lighter-live",
                      "held": {"BTC": "dip_in_uptrend"}}}


# --------------------------------------------------------------- the finding
def test_a_stuck_flatten_pages_once_it_is_stuck_rather_than_slow():
    seen = {}
    rows = [_mum(), _healthy()]
    # first sighting starts the clock and says nothing
    assert fi.flatten_stuck_sickness(rows, seen, NOW) == []
    assert seen["freqtrade-mum-lighter"] == NOW
    # still inside the bar — a flatten legitimately spans a cycle or two
    assert fi.flatten_stuck_sickness(
        rows, seen, NOW + fi.FLATTEN_STUCK_S - 1) == []
    # past it: this is the 6.9h shape
    out = fi.flatten_stuck_sickness(rows, seen, NOW + fi.FLATTEN_STUCK_S + 1)
    assert len(out) == 1, out
    assert out[0]["organ"] == "freqtrade-mum-lighter"


def test_the_healthy_live_book_in_the_same_payload_stays_silent():
    """The (hh) rule: a detector that flags a clean row beside a dirty one is
    a detector the operator learns to ignore."""
    seen = {}
    rows = [_mum(), _healthy()]
    fi.flatten_stuck_sickness(rows, seen, NOW)
    out = fi.flatten_stuck_sickness(rows, seen, NOW + fi.FLATTEN_STUCK_S + 1)
    assert [o["organ"] for o in out] == ["freqtrade-mum-lighter"]
    assert "freqtrade-avo-maria-lighter" not in seen


def test_the_detail_names_the_service_and_the_coins_i8():
    """I8: the operator's action is on a NAMED Railway service holding NAMED
    positions. An opaque row id is a complete diagnosis and an unactionable
    one."""
    seen = {"freqtrade-mum-lighter": NOW}
    out = fi.flatten_stuck_sickness([_mum()], seen, NOW + 25_000)
    d = out[0]["detail"]
    assert "mum-live" in d, d          # the service to open
    assert "1000PEPE" in d, d          # the position still on
    assert "6.9h" in d, d              # how long it has been exposed


# ------------------------------------------------------------- the fail-safes
def test_a_stale_row_is_not_a_live_verdict_i1():
    """I1: a corpse's last word is not a current reading, and DEATH is the
    watchdog's job. A stale row must neither page nor start a clock."""
    seen = {}
    stale = _mum(age=fi.STALE_ROW_S + 60)
    assert fi.flatten_stuck_sickness([stale], seen, NOW) == []
    assert seen == {}
    assert fi.flatten_stuck_sickness([stale], seen, NOW + 100_000) == []


@pytest.mark.parametrize("val", [None, False, 0, "", "true", 1, [], {}])
def test_only_the_literal_true_can_ever_fire(val):
    """Absence is deploy latency, not sickness (the headroom_sickness rule),
    and no junk value may manufacture a page on a real-money book."""
    seen = {}
    row = _mum(flat=val)
    fi.flatten_stuck_sickness([row], seen, NOW)
    assert fi.flatten_stuck_sickness([row], seen, NOW + 100_000) == []
    assert seen == {}


def test_a_book_that_completes_its_flatten_is_forgotten():
    """The clock belongs to the EPISODE. A book that clears must not inherit a
    spent clock, or the next incident pages on its first sighting — and, worse,
    a book that recovers would keep an entry that pages forever."""
    seen = {}
    fi.flatten_stuck_sickness([_mum()], seen, NOW)
    assert "freqtrade-mum-lighter" in seen
    # flatten completes: open 0, key false — mum's actual 23:40Z state
    done = _mum(flat=False, open_n=0)
    assert fi.flatten_stuck_sickness([done], seen, NOW + 60) == []
    assert seen == {}, "a cleared book must be forgotten"
    # a NEW episode starts its own clock and does not page immediately
    assert fi.flatten_stuck_sickness([_mum()], seen, NOW + 120) == []


def test_a_declared_exemption_suppresses_and_the_dict_is_empty_today():
    """The BORN_DARK_OK idiom — the mechanism is tested via injection so the
    shipped dict does not have to be non-empty to prove it works. It IS empty:
    a stuck flatten on a real-money book is the condition this exists for."""
    assert fi.FLATTEN_STUCK_OK == {}, \
        "an exemption here excuses a book from the detector built for it"
    seen = {"freqtrade-mum-lighter": NOW}
    assert fi.flatten_stuck_sickness(
        [_mum()], seen, NOW + 25_000,
        ok={"freqtrade-mum-lighter": "declared"}) == []


def test_junk_input_never_raises():
    for rows in (None, [], [{}], [{"bot": "x"}], [{"extra": None}],
                 [{"extra": {"flatten_incomplete": True}}]):
        fi.flatten_stuck_sickness(rows, {}, NOW)


# ------------------------------------------------- the enforcement is not inert
def _src():
    return (ROOT / "fleet_immune.py").read_text()


def test_the_detector_is_actually_WIRED_into_the_scan():
    """The (iz) class: a declared enforcement that EXISTS and never runs. The
    `(ia)` maxDD bar shipped inert for days behind a bare except. Assert the
    call node by AST, not a substring — a mention in a docstring is not a
    wiring ([[a-substring-test-is-not-a-wiring-test]])."""
    tree = ast.parse(_src())
    run_once = next(n for n in ast.walk(tree)
                    if isinstance(n, ast.FunctionDef) and n.name == "run_once")
    called = {n.func.id for n in ast.walk(run_once)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "flatten_stuck_sickness" in called, \
        "the detector is defined and never called — inert enforcement"


def test_its_memory_is_read_from_and_written_back_to_the_payload():
    """Without persistence every cycle is a first sighting and the sensor can
    NEVER fire — the exact defect `app_seen`/`churn_seen` carry notes about."""
    src = _src()
    assert 'prior.get("flatten_seen")' in src, "memory never restored"
    assert '"flatten_seen": flatten_seen' in src, "memory never persisted"


def test_the_key_we_consume_is_the_key_the_publishers_actually_emit():
    """Test the consumer against what the PUBLISHER builds ((hj)). Both
    real-money-capable hosts must emit this key as a dict key in the published
    extra — if either renames it, this detector goes silently blind on exactly
    the book it was built for."""
    for pub in ("lighter_avo_live_bot.py", "lighter_ticket_taker.py"):
        tree = ast.parse((ROOT / pub).read_text())
        keys = {k.value for n in ast.walk(tree) if isinstance(n, ast.Dict)
                for k in n.keys
                if isinstance(k, ast.Constant) and isinstance(k.value, str)}
        assert "flatten_incomplete" in keys, \
            f"{pub} no longer publishes flatten_incomplete as a dict key"


def test_the_bar_is_far_outside_a_healthy_retry_and_far_inside_the_damage():
    """The one number this detector's sensitivity rests on. The flatten retries
    every loop (90s-5min); the measured incident ran 6.9h (24,840s)."""
    assert 600 <= fi.FLATTEN_STUCK_S <= 7200, fi.FLATTEN_STUCK_S
    assert fi.FLATTEN_STUCK_S < 24_840, \
        "the bar must fire inside the incident it was built from"
