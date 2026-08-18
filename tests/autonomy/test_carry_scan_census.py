"""[2026-08-02] 🌾 CARRY MUST BE ABLE TO NAME ITS OWN BINDING CONSTRAINT.

THE INCIDENT. The book had opened nothing for ~50h while holding 5 of 12 slots
and publishing `hottest_funding_apr` of +245% to +345% against a 20% bar. It
looked like a stall and it was not: the three coins that had cleared the 6h
persistence gate were 1-3 ORDERS OF MAGNITUDE below the $2M liquidity floor
(FOLKS $6k, S $123k, ARC $29k of 24h volume), and the one liquid hot coin
(KAITO, $3.01M) was 0.74h short of persisting. Only 12 of the venue's 203 books
cleared the volume floor at all.

So the correct diagnosis was "working as designed, waiting on liquidity" — but
establishing that took a 40-minute investigation across three sources, because
the book's own log said `scan ok | 217 perps` and its `caps` carried only the
bar and the cap. A reader could not tell "no candidates exist" from "a gate is
blocking" from "the book is broken". That is I8 one layer in.

WHAT IS GUARDED HERE, in priority order:

  1. **The census cannot drift from the gate it explains.** `eligible` is
     asserted equal to the count produced by the REAL candidate expression
     copied from the entry loop. A census that disagrees with the decision is
     worse than none — it would confidently mis-explain the next incident.
  2. The buckets partition the scan (mutually exclusive, summing to `scanned`),
     so a coin cannot be silently uncounted.
  3. The incident itself is a fixture: illiquid-but-hot coins land in `thin`,
     never `eligible`, and the liquid-but-young coin lands in `waiting` with a
     correct ETA.
"""
import ast
import pathlib

import pytest

import funding_carry_bot as carry

pytestmark = pytest.mark.autonomy


def _f(rate, vol, mark=100.0):
    return {"rate": rate, "vol": vol, "mark": mark}


#: Reconstructed from the live payload on the day of the incident. Rates are in
#: the venue's own per-period basis; H and the bar are passed explicitly so this
#: fixture does not silently depend on which arm is configured.
H = 1095.0                 # Lighter quotes per 8h -> 3 * 365 periods/yr
BAR = 0.20                 # 20% TRUE, the bar the live arm gates on
HOT = 0.0004               # * 1095 = 43.8% APR, comfortably over the bar
COLD = 0.00001             # * 1095 = 1.1% APR, under it

T0 = 1_785_600_000.0


def _incident():
    """The 2-Aug cross-section, reduced to its load-bearing shape."""
    fund = {
        "FOLKS": _f(HOT, 5_800),           # hot 21.8h, catastrophically thin
        "S": _f(HOT, 122_600),             # hot 15.9h, thin
        "ARC": _f(HOT, 29_300),            # hot 10.5h, thin
        "KAITO": _f(HOT, 3_011_700),       # hot 5.26h, LIQUID but still proving
        "WTI": _f(HOT, 16_810_000),        # hot 2.85h, liquid, further out
        "BTC": _f(COLD, 50_000_000),       # liquid, funding simply not hot
        "BNB": _f(HOT, 9_000_000),         # already held
        # BOTH cold and thin. Without this row the gate ORDER is untested --
        # swapping the two branches changes no count and the mutation
        # survives. It is the ordering that gives `thin` its meaning: "hot but
        # too illiquid to trade", not "illiquid". On the live venue 155 books
        # are cold and only 40 are thin; under the swapped order `thin` would
        # swallow most of the 155 and the binding constraint would vanish into
        # noise -- the census would still look plausible and mean nothing.
        "DUST": _f(COLD, 1_000),
    }
    positions = {"BNB": {"side": "short_perp"}}
    hot_since = {"FOLKS": T0 - 21.81 * 3600, "S": T0 - 15.85 * 3600,
                 "ARC": T0 - 10.51 * 3600, "KAITO": T0 - 5.26 * 3600,
                 "WTI": T0 - 2.85 * 3600, "BNB": T0 - 40 * 3600}
    return fund, positions, hot_since


def _census():
    fund, positions, hot_since = _incident()
    return carry.scan_census(fund, positions, hot_since, T0, H, BAR)


def test_the_incident_reads_as_liquidity_not_a_stall():
    c = _census()
    assert c["thin"] == 3, c            # FOLKS, S, ARC — hot but untradeable
    assert c["waiting"] == 2, c         # KAITO, WTI — liquid, still persisting
    assert c["cold"] == 2, c            # BTC and DUST
    assert c["held"] == 1, c            # BNB
    assert c["eligible"] == 0, c        # ...hence nothing opened, correctly
    # THE GATE ORDER. DUST is cold AND thin; it must count as COLD, because
    # `thin` earns its meaning ("hot but untradeable") only from being
    # evaluated second. Swapping the branches passes every other assertion.
    assert c["thin"] == 3, "an illiquid COLD book must not inflate `thin`"


def test_it_names_the_next_candidate_and_when():
    """I8: the output must name something the reader can act on -- or wait for."""
    c = _census()
    assert c["next"] == "KAITO", c
    assert abs(c["next_eta_h"] - 0.74) < 0.02, c


def test_buckets_partition_the_scan():
    c = _census()
    assert (c["held"] + c["thin"] + c["cold"] + c["waiting"]
            + c["noncrypto"] + c["eligible"] == c["scanned"] == 8), c


def test_census_cannot_drift_from_the_real_candidate_expression():
    """THE LOAD-BEARING ARM.

    A census that disagrees with the gate would confidently mis-explain the
    next incident. This re-evaluates the entry loop's OWN predicate and
    requires `eligible` to match it, across a spread of cross-sections rather
    than the one fixture -- including cases where coins DO qualify, so the
    agreement is tested in both directions and not only at zero.
    """
    fund, positions, hot_since = _incident()
    # widen the fixture so `eligible` is non-zero in some cells: a test that
    # only ever compares 0 == 0 passes against a census stuck at zero.
    fund["RIPE"] = _f(HOT, 8_000_000)
    hot_since["RIPE"] = T0 - 9 * 3600
    fund["RIPE2"] = _f(-HOT, 4_000_000)          # negative funding also carries
    hot_since["RIPE2"] = T0 - 7 * 3600

    for persist in (0.0, 3.0, 6.0, 12.0, 24.0):
        for min_vol in (0.0, 1e5, 2e6, 1e7, 1e9):
            c = carry.scan_census(fund, positions, hot_since, T0, H, BAR,
                                  min_vol=min_vol, persist_h=persist)
            # verbatim the entry loop's own predicate ((lk) incl. the class
            # screen — the census and the gate move together or this fails)
            real = [x for x in fund.items()
                    if x[0] not in positions
                    and x[1]["vol"] >= min_vol
                    and abs(x[1]["rate"] * H) >= BAR
                    and (T0 - hot_since.get(x[0], T0)) >= persist * 3600.0
                    and carry._class_ok(x[0])]
            assert c["eligible"] == len(real), (
                f"census disagrees with the gate at persist={persist} "
                f"min_vol={min_vol}: {c['eligible']} vs {len(real)}")
    # and the sweep really did exercise the non-zero side
    wide = carry.scan_census(fund, positions, hot_since, T0, H, BAR,
                             min_vol=0.0, persist_h=0.0)
    assert wide["eligible"] >= 5, wide


def test_it_never_raises_on_a_degenerate_scan():
    """Observability must not be able to take a trading loop down."""
    assert carry.scan_census({}, {}, {}, T0, H, BAR)["scanned"] == 0
    assert carry.scan_census(None, None, None, T0, H, BAR)["scanned"] == 0
    assert "next" not in carry.scan_census({}, {}, {}, T0, H, BAR)


def test_a_held_coin_is_counted_once_and_never_as_a_candidate():
    """`held` short-circuits: a held coin must not also be graded on the bar."""
    fund = {"BNB": _f(HOT, 9_000_000)}
    c = carry.scan_census(fund, {"BNB": {}}, {"BNB": T0 - 99 * 3600}, T0, H, BAR)
    assert c == {"scanned": 1, "held": 1, "thin": 0, "cold": 0,
                 "waiting": 0, "noncrypto": 0, "eligible": 0,
                 "waiting_admissible": 0}, c


# ---------------------------------------------------------------------------
# [2026-08-13 (lk)] THE INSTRUMENT-CLASS SCREEN — crypto perps only.
# Era-measured: non-crypto −$14.96/9 closes (every loss a `*_flip` with fees >
# accrued) vs crypto −$0.49/1; mechanism: a closed underlying market satisfies
# PERSIST_H structurally (I7). Offline here, `fleet_bus.is_crypto` runs on its
# hand-list fallback, which carries WTI/SKHYNIXUSD/SPCX — the era's actual
# losers — so these fixtures exercise the same degrade path a dark scout uses.
# ---------------------------------------------------------------------------

def test_a_hot_liquid_persistent_noncrypto_book_is_screened_not_eligible():
    fund = {"WTI": _f(HOT, 16_810_000), "KAITO": _f(HOT, 3_011_700)}
    hot = {"WTI": T0 - 9 * 3600, "KAITO": T0 - 9 * 3600}
    c = carry.scan_census(fund, {}, hot, T0, H, BAR)
    assert c["noncrypto"] == 1 and c["eligible"] == 1, c
    # gate ORDER: class is judged LAST, so the bucket means "blocked by class
    # ALONE" — a cold or thin non-crypto book must not inflate it.
    fund2 = {"WTI": _f(COLD, 16_810_000), "SPCX": _f(HOT, 1_000)}
    c2 = carry.scan_census(fund2, {}, {"SPCX": T0 - 9 * 3600}, T0, H, BAR)
    assert c2["noncrypto"] == 0 and c2["cold"] == 1 and c2["thin"] == 1, c2


def test_the_screen_is_reversible_without_a_deploy(monkeypatch):
    monkeypatch.setattr(carry, "ALLOW_NONCRYPTO", True)
    fund = {"WTI": _f(HOT, 16_810_000)}
    c = carry.scan_census(fund, {}, {"WTI": T0 - 9 * 3600}, T0, H, BAR)
    assert c["eligible"] == 1 and c["noncrypto"] == 0, c


def test_a_missing_fleet_bus_fails_open(monkeypatch):
    """An import regression must not shrink the book's universe — the
    dark-scout fallback INSIDE `is_crypto` is the load-bearing degrade."""
    monkeypatch.setattr(carry, "fleet_bus", None)
    fund = {"WTI": _f(HOT, 16_810_000)}
    c = carry.scan_census(fund, {}, {"WTI": T0 - 9 * 3600}, T0, H, BAR)
    assert c["eligible"] == 1 and c["noncrypto"] == 0, c


def test_the_entry_loop_itself_carries_the_screen():
    """AST, not a substring scan (the (hm) lesson): the `candidates`
    generator in main() must call `_class_ok`. The drift test above pins the
    census to a COPY of the predicate; this pins the real one, so removing
    the screen from the entry loop alone cannot pass."""
    tree = ast.parse(pathlib.Path(carry.__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if (isinstance(node, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "candidates"
                        for t in node.targets)):
            calls = {c.func.id for c in ast.walk(node.value)
                     if isinstance(c, ast.Call)
                     and isinstance(c.func, ast.Name)}
            assert "_class_ok" in calls, (
                "the entry loop's candidate filter no longer screens class")
            return
    raise AssertionError("candidates assignment not found in main()")


# ---------------------------------------------------------------------------
# [2026-08-03 (is)] THE CENSUS MUST NOT BE ABLE TO STOP THE BOOK.
# ---------------------------------------------------------------------------

def test_scan_census_raises_on_a_malformed_entry_which_is_why_the_call_is_guarded():
    """The census is NOT total over its input, and that is the whole reason the
    call site needs a guard. It indexes `f["rate"]` / `f["vol"]` directly, so a
    funding entry missing either key — or carrying a None rate — raises.

    `funding_map()` always seeds those keys today, so this is a latent rather
    than live failure; the point is that the loop must not DEPEND on that
    remaining true, because the census runs UNCONDITIONALLY while the trading
    path below it is gated on a free slot.
    """
    for bad in ({"A": {"rate": 0.001}},          # no vol
                {"A": {"vol": 5e6}},             # no rate
                {"A": {"rate": None, "vol": 5e6}}):
        with pytest.raises((KeyError, TypeError)):
            carry.scan_census(bad, {}, {}, 0.0, 1095.0, 0.2)


def test_the_census_call_site_is_exception_guarded():
    """AST, not a substring scan — the prose above says the words 'try' and
    'except' and a page-wide grep would pass on the comment alone (the (hm)
    lesson). Asserts the `scan_census(...)` call in main() is lexically inside
    a `try` whose handler catches a bare Exception.

    Mutation that turns this red: unwrap the call.
    """
    tree = ast.parse(pathlib.Path(carry.__file__).read_text(encoding="utf-8"))

    guarded = unguarded = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        catches_broad = any(
            h.type is None
            or (isinstance(h.type, ast.Name) and h.type.id == "Exception")
            for h in node.handlers)
        for sub in ast.walk(node):
            if (isinstance(sub, ast.Call)
                    and isinstance(sub.func, ast.Name)
                    and sub.func.id == "scan_census"
                    and catches_broad):
                guarded += 1

    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "scan_census"):
            unguarded += 1

    assert guarded >= 1, "scan_census() is called outside any try/except"
    assert guarded == unguarded, (
        f"{unguarded - guarded} scan_census() call(s) are unguarded — an "
        "observability feature must never be able to stop the trading loop")


def test_the_degraded_census_carries_every_key_the_consumers_read():
    """A partial fallback would move the failure one line down into the log
    line / `extra.scan` instead of preventing it."""
    src = pathlib.Path(carry.__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)
    fallback = None
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        if not any(isinstance(s, ast.Call) and isinstance(s.func, ast.Name)
                   and s.func.id == "scan_census" for s in ast.walk(node)):
            continue
        for h in node.handlers:
            for stmt in h.body:
                if (isinstance(stmt, ast.Assign)
                        and isinstance(stmt.value, ast.Dict)):
                    fallback = {k.value for k in stmt.value.keys}
    assert fallback, "no dict fallback found in the census handler"
    required = {"scanned", "held", "thin", "cold", "waiting", "noncrypto",
                "eligible", "waiting_admissible"}
    assert required <= fallback, f"degraded census missing {required - fallback}"


def test_next_never_promises_a_coin_the_class_screen_will_refuse():
    """[18-Aug (qc)] The live payload read `next: SKHYNIXUSD / next_eta_h
    3.75` on a crypto_only book — the `waiting` branch picked `next` BEFORE
    the class screen (which is deliberately LAST in gate order), so the row
    promised an open the gate order guarantees to refuse (I8: the operator
    misreads the coming refusal as a stall). `next` must be the soonest
    ADMISSIBLE waiter; the screened coin still counts as `waiting`."""
    # SKHYNIXUSD: hot, liquid, 2.25h into a 6h persistence -> eta 3.75h.
    # KAITO: hot, liquid, crypto, only 1h in -> eta 5h (LATER than SKHYNIX).
    fund = {"SKHYNIXUSD": _f(HOT, 30_100_000), "KAITO": _f(HOT, 3_011_700)}
    hot = {"SKHYNIXUSD": T0 - 2.25 * 3600, "KAITO": T0 - 1.0 * 3600}
    c = carry.scan_census(fund, {}, hot, T0, H, BAR)
    assert c["waiting"] == 2, c            # the bucket contract is untouched
    assert c["next"] == "KAITO", c         # the sooner NON-admissible coin lost
    assert c["next_eta_h"] == pytest.approx(5.0, abs=0.01), c
    # With ONLY the screened coin waiting there is no honest promise at all.
    c2 = carry.scan_census({"SKHYNIXUSD": _f(HOT, 30_100_000)}, {},
                           {"SKHYNIXUSD": T0 - 2.25 * 3600}, T0, H, BAR)
    assert c2["waiting"] == 1 and "next" not in c2, c2


def test_waiting_with_no_next_says_whether_any_waiter_is_admissible():
    """[19-Aug (qg)] `(qc)` correctly stopped `next` promising a coin the class
    screen will refuse — and left `waiting N / no next` meaning two different
    things: "the soonest admissible waiter is still being picked" vs "every
    waiter will be REFUSED when its clock runs out". Measured on the live row
    the morning after (`waiting 3`, no `next`), the daily review could not tell
    which without rebuilding the gate by hand — the second-copy trap (hj).

    `waiting_admissible` is the disambiguator, and it is a SUB-COUNT of
    `waiting`, never a bucket, so the partition contract is untouched."""
    # ALL waiters class-refused -> no promise, and the census says why.
    only_screened = carry.scan_census(
        {"SKHYNIXUSD": _f(HOT, 30_100_000), "BRENTOIL": _f(HOT, 12_000_000)},
        {}, {"SKHYNIXUSD": T0 - 2.25 * 3600, "BRENTOIL": T0 - 1.0 * 3600},
        T0, H, BAR)
    assert only_screened["waiting"] == 2, only_screened
    assert "next" not in only_screened, only_screened
    assert only_screened["waiting_admissible"] == 0, only_screened

    # A mixed cross-section: the count tracks the ADMISSIBLE subset only.
    mixed = carry.scan_census(
        {"SKHYNIXUSD": _f(HOT, 30_100_000), "KAITO": _f(HOT, 3_011_700)},
        {}, {"SKHYNIXUSD": T0 - 2.25 * 3600, "KAITO": T0 - 1.0 * 3600},
        T0, H, BAR)
    assert mixed["waiting"] == 2, mixed
    assert mixed["waiting_admissible"] == 1, mixed
    assert mixed["next"] == "KAITO", mixed

    # THE INVARIANT that makes the log line honest: a promise exists if and
    # only if at least one waiter is admissible.
    for c in (only_screened, mixed, _census()):
        assert ("next" in c) == (c["waiting_admissible"] > 0), c
        assert c["waiting_admissible"] <= c["waiting"], c


def test_waiting_admissible_is_not_a_bucket_and_never_breaks_the_partition():
    """It counts a SUBSET of `waiting`, so adding it to the partition sum would
    double-count. This pins the contract the (qg) counter must not break."""
    c = _census()
    assert (c["held"] + c["thin"] + c["cold"] + c["waiting"]
            + c["noncrypto"] + c["eligible"] == c["scanned"]), c
    # The 2-Aug fixture is itself a mixed cell, which is the point: KAITO and
    # WTI are BOTH waiting, but WTI is oil — so `waiting` is 2 while only one
    # of them can ever be opened. Counting the admissible subset is exactly
    # what tells the reader that.
    assert c["waiting"] == 2 and c["waiting_admissible"] == 1, c
    assert c["next"] == "KAITO", c
