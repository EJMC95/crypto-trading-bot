"""🔭 The entry-cell observer: publish-only, and it must not be able to lie
about what it did not look at.

WHY THIS FILE EXISTS. The observer's whole output is three counts, and every
one of them has a way of being silently wrong that this repo has already paid
for at least once:

  * `missed_n` reads **0** when the venue list is dark — so the instrument
    built to say *"a wider universe would have shown her something"* would
    publish the opposite conclusion from its own blindness. This happened on
    the module's FIRST live run (an unset DATABASE_URL), which is why
    `venue_basis` exists and is pinned here.
  * `open_n` counts a name the entry site **refuses** — so an opening on a
    non-crypto book the per-asset oracle cannot grade would argue for a
    universe widening that could not reach it. Measured on 👩 mum 11-Sep:
    three of the six names under her RSI bar were exactly that.
  * a **dwell** closes because the observer's own fetch budget skipped the
    coin, turning its governance into a measurement about itself — the (ml)
    stale-reader shape on the reporting side.

The selftest (`entry_cell_observer.py --selftest`, registered in
`tests/test_selftests.py`) drives the arithmetic; 16 of 16 mutations redden it,
with a positive control that correctly survives. THIS file pins the two things
a selftest structurally cannot: that the module stays publish-only, and that it
calls the books' own code instead of keeping a copy of it.
"""
import ast
from pathlib import Path

import pytest

import entry_cell_observer as obs

ROOT = Path(__file__).resolve().parent.parent.parent
SRC = ROOT / "entry_cell_observer.py"


# ---------------------------------------------------------------------------
# PUBLISH-ONLY. The `fleet_allocation` contract: an advisory organ is proved
# advisory by the absence of actuator call sites, not by its docstring.

#: Names that would make this module an actuator. `save_state` is allowed and
#: is the ONLY write: it carries the organ's own reading and dwell memory.
FORBIDDEN = (
    "write_levers",       # the growth rail's lever writer
    "get_lever",          # reading a lever is how a consumer starts
    "market_open",        # the books' order entry
    "place_order", "create_order", "submit_order",
    "apply_tuning",       # a book's lever consumption
    "publish",            # bot_pnl_store.publish = a dashboard ROW (I22: an
                          # instrument does not get a row)
)


def _calls(src):
    """Every called name in the module, attribute calls flattened to the
    attribute (so `store.publish(...)` reads as `publish`)."""
    out = set()
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Attribute):
                out.add(f.attr)
            elif isinstance(f, ast.Name):
                out.add(f.id)
    return out


@pytest.mark.parametrize("name", FORBIDDEN)
def test_the_observer_is_publish_only(name):
    """It moves no capital, writes no lever, places no order and takes no row.

    Found by AST rather than by grep: the word `publish` appears a dozen times
    in this module's own prose, and a substring scan would pass on a real call
    site sitting beside it — the documented page-wide-scan failure.
    """
    assert name not in _calls(SRC.read_text()), (
        f"entry_cell_observer calls `{name}` — it is an INSTRUMENT, and the "
        "moment it acts it needs the whole evidence ladder in front of it")


def test_the_only_write_is_its_own_state_key():
    """One writer, one key. A second `save_state` target would let the
    instrument scribble on an organ it is supposed to be observing."""
    src = SRC.read_text()
    targets = []
    for n in ast.walk(ast.parse(src)):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "save_state" and n.args):
            a = n.args[0]
            targets.append(a.id if isinstance(a, ast.Name)
                           else getattr(a, "value", None))
    assert targets == ["STATE_KEY"], (
        f"save_state targets {targets} — expected exactly [STATE_KEY]")
    assert obs.STATE_KEY == "entry-cell-observer"


def test_it_never_builds_a_lighter_client_that_can_sign():
    """The structural half of publish-only: no signer, so no order is reachable
    even from a future edit that forgot this file."""
    src = SRC.read_text()
    for n in ast.walk(ast.parse(src)):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id == "LighterClient"):
            kw = {k.arg: k.value for k in n.keywords}
            assert "with_signer" in kw, "LighterClient built without naming with_signer"
            assert kw["with_signer"].value is False, (
                "the observer must build a read-only client")
            return
    pytest.fail("no LighterClient construction found — did the venue read move?")


# ---------------------------------------------------------------------------
# NO SECOND COPY OF A RULE. The cell, the universe and the entry gate all
# belong to the books; this module may only CALL them.

def test_the_cell_is_the_books_own_signals_call():
    """`observe_carrier` evaluates `carrier.signals(...)` and nothing else.

    A re-implementation of the entry rule here would drift from the books
    within a week, and the measurement would then be about this file.
    """
    src = SRC.read_text()
    assert "carrier.signals(bars, extra_for(sym))" in src, (
        "the observer no longer calls the carrier's own signals()")
    # None of the rule's own indicators may be computed here.
    for banned in ("rsi_series", "ema_series", "def rsi", "def ema"):
        assert banned not in src, (
            f"entry_cell_observer computes `{banned}` — that is a second copy "
            "of the entry rule; call the carrier instead")


def test_the_universe_and_the_gate_come_from_their_declared_owners():
    """`carrier_universe` and `noncrypto_entry_blocked` are the one owners of
    "what does this book scan" and "would its entry site admit this name"."""
    src = SRC.read_text()
    assert "fam.carrier_universe(s)" in src
    assert "_f.noncrypto_entry_blocked(sym, r_up)" in src
    assert "fam.noncrypto_regimes()" in src, (
        "the oracle verdict map must be the one the live entry site reads — "
        "passing {} makes every non-crypto name fail-closed and the observer "
        "then disagrees with the bot it measures")


# ---------------------------------------------------------------------------
# THE THREE COUNTS. Behaviour, driven rather than asserted about.

def _carrier(bar=42.0):
    class _C:
        bot, tf, RSI_MAX = "book", "1h", bar

        def signals(self, bars, extra):
            r = bars["rsi"]
            return {"enter": "go" if r < self.RSI_MAX else None,
                    "rsi": r, "uptrend": False, "vol": 1.0}
    return _C()


def _bars_for(reading):
    def f(sym):
        return {"t": [1], "rsi": reading[sym]} if sym in reading else None
    return f


def test_a_gate_blocked_opening_is_in_neither_headline_count():
    """The measurement the instrument turns on. An opening the entry site
    refuses is not actionable AND not missed — no universe change reaches it."""
    reading = {"AAA": 30.0, "ZZZ": 20.0, "BLK": 25.0}
    o, _ = obs.observe_carrier(
        _carrier(), list(reading), ["AAA", "BLK"], _bars_for(reading),
        lambda s: {}, rsi_bar=42.0, admits=lambda s: s != "BLK")
    assert o["actionable_n"] == 1 and o["open_in_universe"] == ["AAA"]
    assert o["missed_n"] == 1 and o["open_missed"] == ["ZZZ"]
    assert o["gate_blocked_n"] == 1 and o["open_gate_blocked"] == ["BLK"]
    assert o["open_n"] == 3                     # counted once, and all counted
    assert o["actionable_n"] + o["missed_n"] + o["gate_blocked_n"] == o["open_n"]


def test_an_unreadable_gate_refuses_rather_than_admits():
    """Fail-closed, the direction the live entry site fails in. An instrument
    must not call an opening actionable because its own gate check broke."""
    reading = {"AAA": 30.0}

    def boom(sym):
        raise RuntimeError("oracle down")

    o, _ = obs.observe_carrier(_carrier(), ["AAA"], ["AAA"],
                               _bars_for(reading), lambda s: {},
                               rsi_bar=42.0, admits=boom)
    assert o["gate_blocked_n"] == 1 and o["actionable_n"] == 0


def test_a_dark_venue_list_is_partial_and_never_a_clean_zero():
    """THE INCIDENT, in this module's own first live run. With no venue list
    the observer sees only each book's own names, so `missed_n` would read 0 —
    the exact opposite of the claim it exists to test (I1/I6)."""
    dark = obs.build_payload([], 0, 5, 0, 0.0, venue_basis="dark")
    assert dark["venue_basis"] == "dark"
    assert dark["coverage"]["basis"] == "partial", (
        "a dark venue list must never publish a complete basis")
    lit = obs.build_payload([], 200, 200, 0, 0.0, venue_basis="scout")
    assert lit["coverage"]["basis"] == "complete"


def test_an_uncovered_coin_carries_its_dwell_instead_of_closing_it():
    """The budget is governance, not a measurement. A coin the sweep skipped
    must keep its open stance, or the organ manufactures short dwells out of
    its own fetch cap."""
    st, closed = obs.dwell_step({}, {"AAA": True}, ["AAA"], 0.0)
    assert closed == []
    st, closed = obs.dwell_step(st, {}, ["AAA"], 600.0)     # not looked at
    assert closed == [] and st["open_since"]["AAA"]["ts"] == 0.0
    st, closed = obs.dwell_step(st, {"AAA": False}, ["AAA"], 900.0)
    assert closed[0]["secs"] == 900.0, (
        "the dwell clock must run from the original open, not from the last "
        "cycle that happened to cover the coin")


def test_a_blocked_opening_never_enters_the_dwell_memory():
    """Its duration is not a reaction-time question: no reaction was available.
    The control is the same reading WITHOUT the block, which does record it."""
    blocked, _ = obs.dwell_step({}, {"BLK": True}, [], 0.0, blocked=["BLK"])
    assert blocked["open_since"] == {} and blocked["missed_counts"] == {}
    assert blocked["cycles"]["with_open_venue"] == 0
    free, _ = obs.dwell_step({}, {"BLK": True}, [], 0.0)
    assert "BLK" in free["open_since"] and free["missed_counts"] == {"BLK": 1}
    assert free["cycles"]["with_open_venue"] == 1


def test_no_dwell_samples_reads_dark_not_zero():
    """0 seconds and "never measured" are different facts (I1). A consumer
    must be able to tell them apart, and the resolution publishes beside them
    so no reader mistakes a quantisation floor for a duration."""
    d = obs.summarize_dwell([], 300)
    assert d == {"n": 0, "median_s": None, "p90_s": None, "max_s": None,
                 "resolution_s": 300}
    assert obs.summarize_dwell([60, 120], 300)["resolution_s"] == 300


def test_the_volume_term_is_named_from_the_books_own_field():
    """The one live refusal the instrument could not name until
    `OversoldRebound.signals` published `vol` (I23: the gate records the
    quantity it cuts). A carrier that publishes no `vol` stays `opaque` — an
    inferred term would be a second copy of the rule."""
    shut = {"enter": None, "rsi": 30.0, "uptrend": False, "vol": 0.0}
    assert obs.refusal_reason(shut, rsi_bar=42.0) == "no_volume"
    assert obs.refusal_reason({k: v for k, v in shut.items() if k != "vol"},
                              rsi_bar=42.0) == "opaque"


def test_mums_live_carrier_publishes_the_volume_term():
    """The field the observer reads, asserted on the REAL carrier rather than
    on a fixture the observer's author wrote ((hj)'s payload-contract rule:
    drive the publisher, never a hand-built lookalike)."""
    import lighter_family_bot as fam
    S = [s for s in fam.live_strategies() if s.bot == "freqtrade-mum"][0]
    n = S.min_bars + 30
    bars = {"c": [100.0 + (i % 7) * 0.1 for i in range(n)],
            "h": [101.0] * n, "l": [99.0] * n, "v": [0.0] * n,
            "t": list(range(n))}
    sig = S.signals(bars, {"btc_regime_up": True})
    assert sig is not None and "vol" in sig, (
        "OversoldRebound no longer publishes `vol` — the observer's "
        "`no_volume` verdict degrades to `opaque` without it")
    assert sig["vol"] == 0.0 and sig["enter"] is None
    assert obs.refusal_reason(sig, rsi_bar=S.RSI_MAX).endswith("no_volume")


def test_non_finite_never_reaches_the_published_row():
    """I5: a bad field becomes null and the row still writes."""
    import json
    assert obs._finite(float("nan")) is None
    assert obs._finite(float("inf")) is None
    assert obs.summarize_dwell([float("nan"), 10.0], 300)["n"] == 1
    o, _ = obs.observe_carrier(_carrier(), ["AAA"], ["AAA"],
                               _bars_for({"AAA": 30.0}), lambda s: {},
                               rsi_bar=42.0)
    p = obs.build_payload([dict(o, bot="book", cycles={"n": 1})], 1, 1, 0, 0.0)
    json.dumps(p, allow_nan=False)        # what storage would accept


def test_the_payload_states_its_own_ceiling():
    """`missed_n` is an upper bound, and a reader who meets it on a dashboard
    must meet that fact there too — not only in this repo's prose ((gl): a
    detector that overstates is one the operator learns to ignore)."""
    lim = " ".join(obs.build_payload([], 1, 1, 0, 0.0)["limits"])
    assert "upper bound" in lim and "not edge" in lim
    assert "gate_blocked_n" in lim


def test_it_is_declared_unpageable_and_has_a_vitals_row():
    """The (iy) shape: an organ with no ORGAN_SPECS row is worse than
    unpageable, it is invisible. A publish-only instrument may be non-critical
    — it must not be undeclared."""
    from tests.autonomy.test_organ_pageability import UNPAGEABLE_OK, specs
    by_key = {k: (c, t) for k, c, t in specs()}
    assert obs.STATE_KEY in by_key, (
        f"{obs.STATE_KEY} has no ORGAN_SPECS row — it would publish with no "
        "vitals card and its death would be invisible")
    assert obs.STATE_KEY in UNPAGEABLE_OK, (
        "declare it unpageable with a reason, or mark it critical")
