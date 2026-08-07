"""[(lj)] I10's real-money gate must look the book up by the key its PUBLISHER writes.

`golive_blocker` is CLAUDE.md's declared enforcement for I10 — *"real money is
gated by published evidence, in code"*. It looked the book up as

    state["books"].get("perps-funding-spread")          # the bare base

while `scripts/golive_readiness.py` keys `payload_books` by the LEDGER's `bot`
column, which is `ctx.bot_id` = `BOT + _SUFFIX[mode]` —
`perps-funding-spread-lighter` live, `-lshadow` shadow. So the lookup could
**never** match: the gate always returned *"go-live gate has no entry for
perps-funding-spread"*.

Fail-closed, so there was never an unsafe admit — but I10's gate was
structurally UNPASSABLE. The operator could set `FUNDSPREAD_GOLIVE=1` on a
genuinely READY book and still be refused, for a reason that reads like the
grader not knowing the book exists.

**Fourth instance of the bare-vs-suffixed key class in this fleet** (`FEE_RT`,
`ERA_START`, `era_epoch_for` — each documented in CLAUDE.md, each shipped
anyway). And the bot's own selftest could not see it, because its `_payload`
fixture keyed `books` by `BOT` too: consumer and fixture agreed with each other
and both disagreed with the publisher. That is the `(hj)` class verbatim — *"a
consumer is tested against a payload its publisher built. Never hand-write a
fixture that 'looks like' the payload."*

So this file does not hand-write one. It drives the REAL grader's publish path
and feeds what it actually wrote to the REAL gate.
"""
import sys
import time
import types
from datetime import datetime, timedelta, timezone

import pytest

pytestmark = [pytest.mark.real_money, pytest.mark.autonomy]

import scripts.golive_readiness as GR          # noqa: E402
import lighter_funding_spread_bot as FS        # noqa: E402

LIVE_ROW = FS.BOT + "-lighter"
SHADOW_ROW = FS.BOT + "-lshadow"


class _Store:
    """Records what the grader publishes; no DB."""

    def __init__(self, rows):
        self.rows = rows
        self.writes = {}

    def fetch_paper_trades(self, limit=None):
        return list(self.rows)

    def fetch_bot_pnl(self):
        return []

    def load_state(self, key):
        return self.writes.get(key)

    def load_state_checked(self, key):
        return True, self.writes.get(key)

    def fetch_state_history(self, key, limit=None):
        return []

    def save_state(self, key, payload):
        self.writes[key] = payload
        return True

    def save_history(self, key, payload):
        return True


def _winning_ledger(bot, n=40, days=45):
    """A book that genuinely clears the bars, so `ready` is True on merit.

    A little variance on purpose: an exactly-constant return gives a degenerate
    t (~1e16), which passes the bar for the wrong reason and would hide a real
    regression in the statistic.
    """
    t0 = datetime.now(timezone.utc) - timedelta(days=days)
    out = []
    for i in range(n):
        close = t0 + timedelta(days=i * (days - 1) / (n - 1))
        _r = 0.02 + (0.004 if i % 3 == 0 else -0.002)
        out.append({"bot": bot, "pair": "BTC/USDC",
                    "profit_abs": 250.0 * _r, "profit_ratio": _r,
                    "enter_tag": "long", "exit_reason": "tp",
                    "duration_min": 60.0,
                    "open_ts": close - timedelta(hours=1), "close_ts": close,
                    "is_open": False, "venue": "lighter",
                    "open_rate": 100.0, "close_rate": 102.0, "extra": {}})
    return out


def _publish(rows):
    """Run the REAL grader and return the payload it wrote."""
    store = _Store(rows)
    shim = types.ModuleType("bot_pnl_store")
    for n in ("fetch_paper_trades", "fetch_bot_pnl", "load_state",
              "load_state_checked", "fetch_state_history", "save_state",
              "save_history"):
        setattr(shim, n, getattr(store, n))
    real, argv = sys.modules.get("bot_pnl_store"), sys.argv
    sys.modules["bot_pnl_store"] = shim
    sys.argv = ["golive_readiness.py", "--publish", "--min-closes", "1"]
    try:
        GR.main()
    finally:
        sys.argv = argv
        if real is None:
            sys.modules.pop("bot_pnl_store", None)
        else:
            sys.modules["bot_pnl_store"] = real
    return store.writes.get(GR.KEY)


@pytest.fixture
def armed(monkeypatch):
    monkeypatch.setenv("FUNDSPREAD_GOLIVE", "1")


@pytest.fixture
def no_era(monkeypatch):
    """Isolate the KEY FORM from the era precondition.

    `perps-funding-spread` carries a real POLICY_ERA of 2026-07-17, so its
    in-era window cannot reach the 30-day bar today and no synthetic ledger can
    make it READY. The era rule is correct and is tested elsewhere; what is
    under test here is which KEY the gate reads, so the era is stood down for
    the two cases that need a genuinely ready book.
    """
    monkeypatch.setattr(GR, "POLICY_ERA", {}, raising=False)


def test_the_publisher_keys_books_by_the_suffixed_row_id():
    """The premise, established from the publisher rather than asserted."""
    payload = _publish(_winning_ledger(LIVE_ROW))
    assert payload and payload.get("books"), payload
    assert LIVE_ROW in payload["books"], (
        f"expected the grader to key `books` by the row id; got "
        f"{sorted(payload['books'])}")
    assert FS.BOT not in payload["books"], (
        "the grader does NOT key by the bare base — the gate must not either")


def test_the_gate_finds_a_ready_book_in_a_real_published_payload(armed, no_era):
    """THE INCIDENT. Against the publisher's own output the old lookup returned
    'go-live gate has no entry for perps-funding-spread' on a READY book."""
    payload = _publish(_winning_ledger(LIVE_ROW))
    assert payload["books"][LIVE_ROW]["ready"] is True, payload["books"][LIVE_ROW]
    assert FS.golive_blocker(LIVE_ROW, payload, time.time()) is None, (
        FS.golive_blocker(LIVE_ROW, payload, time.time()))


def test_the_bare_base_lookup_can_never_match(armed, no_era):
    """The regression: reverting the call site to `BOT` refuses a ready book."""
    payload = _publish(_winning_ledger(LIVE_ROW))
    why = FS.golive_blocker(FS.BOT, payload, time.time())
    assert why and "no entry" in why, why


def test_the_call_site_passes_the_row_id_not_the_bare_base():
    """Wiring: `golive_blocker(BOT)` at the call site restores the bug even
    with the function itself correct."""
    import ast
    import pathlib
    src = pathlib.Path(FS.__file__).read_text()
    tree = ast.parse(src)
    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == "golive_blocker" and n.args]
    # the production call site is the one with a single argument
    prod = [c for c in calls if len(c.args) == 1]
    assert prod, "could not find the production golive_blocker call"
    for c in prod:
        arg = ast.unparse(c.args[0])
        assert arg != "BOT", (
            f"line {c.lineno}: the gate is looked up by the bare base, which "
            "the publisher never writes")
        assert "bot_id" in arg, (
            f"line {c.lineno}: expected the venue-suffixed row id, got {arg!r}")


def test_a_not_ready_book_is_still_refused(armed):
    """Control group: the fix must not turn the gate into a rubber stamp."""
    payload = _publish(_winning_ledger(LIVE_ROW, n=5, days=3))
    why = FS.golive_blocker(LIVE_ROW, payload, time.time())
    assert why and "NOT ready" in why, why


def test_the_shadow_row_is_a_different_book_to_the_gate(armed, no_era):
    """The suffix is not cosmetic: a READY shadow twin must not arm the live
    arm. This is why the fix is the exact row id and not a tolerant match on
    either form."""
    payload = _publish(_winning_ledger(SHADOW_ROW))
    assert SHADOW_ROW in payload["books"]
    why = FS.golive_blocker(LIVE_ROW, payload, time.time())
    assert why and "no entry" in why, (
        "a ready SHADOW row armed the LIVE arm — the gate must key on the arm "
        f"that is actually trading: {why}")
