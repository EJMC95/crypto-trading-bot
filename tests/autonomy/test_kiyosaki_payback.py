"""[2026-08-27] 🏦 RICH DAD'S PAYBACK VELOCITY TIGHTENED 120h -> 48h — PIN THE
VALUE, THE DERIVATION, THE DIRECTION, THE BLAST RADIUS, AND THE CLASS SCREEN.

`payback_max_h` is not a cost knob, it is THE ENTRY BAR: the gate refuses any
coin whose funding cannot repay the modelled 30bps round trip inside the
window, so the bar it implies is `RT * 8760 / payback_h`. At 120h that was
~21.9% TRUE — the loosest bar in the funding cohort, barely above the 20%
floor it inherited — and it admitted coins that pay for ~2 days and then sit
at a resting default for the other 12. This book cannot sell those: its
`EXIT_APR` (0.01875) is 5.6x below the crypto resting pin, so a pinned coin
never reaches `decay_paid`, never flips to `liability_flip`, and rides to
`max_hold` 336h later. 4 of the 6 coins it held at the time of the change had
already reverted to a pin (ZEC 10.5, AAVE 10.5, HYPE 10.5, NBIS 3.5).

MEASURED on the book's own cell (the I19 price, both directions):
    120h: 19.0 closes/30d, mean +0.0145, t=+0.26, I16 LB 0.000,
          h2 NEGATIVE (-0.43), $ALL/30d +$1.20
     48h: 11.0 closes/30d (-42%), mean +0.1630 (11x), t=+2.00, LB +0.059,
          BOTH halves positive (+1.65/+1.93), $ALL/30d +$2.70 (+125%)
A broad PLATEAU, not a spike: 42h +$2.52 · 48h +$2.70 · 54h +$2.62 ·
60h +$2.43, monotone away (84h +$1.78, 120h +$1.20). 48h is also the value
🌾 carry independently runs (`CARRY_PAYBACK_MAX_H`).

REFUSED with its number: differentiating from carry by BAND instead (admit
only [21.9%, 36.5%), disjoint from carry) reads n=3, mean -0.169, t=-2.65,
BOTH HALVES NEGATIVE — the supply this book would hold exclusively loses
money on its own. The edge is at the TOP of the ranking, which carry takes
too. Tightening beats carving.

FIVE PINS, each mutation-verified:
  1. The default IS 48.0, and the env escape hatch still reverses it.
  2. The effective bar is DERIVED — `effective_entry_bar` is the exact
     inverse of `payback_hours`, it is the ONE owner of that arithmetic, and
     it is PUBLISHED on the row (`caps.payback_bar_true`), because a reader
     that only sees `enter_apr` models this book 2.5x too loose.
  3. RESTRICT-DIRECTION, driven: at 48h the gate admits a strict SUBSET of
     what it admitted at 120h, on the same fixture. Not argued from
     monotonicity — run.
  4. ENTRY-ONLY: `cashflow_exit` cannot see the knob (AST) and returns
     identical verdicts across every setting of it (driven), and a HELD coin
     short-circuits before the payback check, so nothing open is evicted.
  5. The crypto-only CODE default is crypto-only when the env is unset —
     which is the half the live service currently overrides, so the code
     must not quietly agree with the drift.
"""
import ast
import copy
import importlib
import pathlib

import pytest

import lighter_book_kiyosaki_bot as rd

pytestmark = pytest.mark.autonomy

_SRC = pathlib.Path(rd.__file__)
_TREE = ast.parse(_SRC.read_text(encoding="utf-8"))

T0 = 1_785_600_000.0
#: the shipped window and the one it replaced — every direction claim below is
#: made against BOTH, never against monotonicity taken on trust.
SHIPPED_H, PRIOR_H = 48.0, 120.0


def _reload_with(monkeypatch, name, value):
    """Reload the module under a controlled env. Reload mutates the module
    object in place, so every other test module's `rd` reference stays valid;
    the caller restores with `_reload_with(monkeypatch, name, None)`."""
    if value is None:
        monkeypatch.delenv(name, raising=False)
    else:
        monkeypatch.setenv(name, value)
    importlib.reload(rd)


def _env_default(var):
    """The SHIPPED default for `os.environ.get(var, <default>)`, read out of
    the source by AST. Pinning the literal rather than the imported constant
    is what keeps this honest when the runner's own environment sets the var
    — a green test that merely echoes the runner's env is the vacuous kind."""
    found = []
    for node in ast.walk(_TREE):
        if not (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "get"):
            continue
        args = node.args
        if len(args) == 2 and isinstance(args[0], ast.Constant) \
                and args[0].value == var and isinstance(args[1], ast.Constant):
            found.append(args[1].value)
    assert len(found) == 1, (
        f"expected exactly one os.environ.get({var!r}, <default>) site, "
        f"found {len(found)} — a second reader is a second rule ((hj))")
    return found[0]


def _fund(aprs, vol=5e6):
    """A funding map denominated in TRUE apr, converted through the module's
    own basis constant so the fixture cannot drift from the gate's units."""
    return {f"C{i}": {"rate": a / rd.H, "vol": vol}
            for i, a in enumerate(aprs)}


# --- 1. the value -----------------------------------------------------------
def test_the_shipped_payback_default_is_forty_eight_hours(monkeypatch):
    assert _env_default("RICHDAD_PAYBACK_MAX_H") == "48", (
        "the payback window moved off the measured 48h — a revert to 120h "
        "costs the book its only measured claim (t +2.00 -> +0.26, both "
        "halves -> h2 negative) and needs its own measurement, not a tidy-up")
    _reload_with(monkeypatch, "RICHDAD_PAYBACK_MAX_H", None)
    assert rd.PAYBACK_MAX_H == SHIPPED_H


def test_the_env_override_reverses_it_without_a_deploy(monkeypatch):
    try:
        _reload_with(monkeypatch, "RICHDAD_PAYBACK_MAX_H", "120")
        assert rd.PAYBACK_MAX_H == PRIOR_H, (
            "RICHDAD_PAYBACK_MAX_H no longer reaches the gate — the "
            "no-deploy escape hatch is the condition every gate move here "
            "ships on")
        assert rd.effective_entry_bar() == pytest.approx(
            rd.RT_COST_FRAC * rd.HOURS_PER_YEAR / PRIOR_H), \
            "the derived bar must follow the env, not a frozen constant"
    finally:
        _reload_with(monkeypatch, "RICHDAD_PAYBACK_MAX_H", None)
    assert rd.PAYBACK_MAX_H == SHIPPED_H


# --- 2. the derivation ------------------------------------------------------
def test_the_effective_bar_is_the_exact_inverse_of_the_gates_own_function():
    """Driven, not restated: for every window, the bar it implies is the apr
    whose payback IS that window. If someone retypes the arithmetic wrong
    anywhere, the round trip stops closing."""
    for ph in (12.0, 24.0, SHIPPED_H, 72.0, PRIOR_H, 336.0):
        bar = rd.effective_entry_bar(ph)
        assert rd.payback_hours(bar) == pytest.approx(ph, rel=1e-9), (ph, bar)
        # and the gate itself agrees at the boundary: a hair above the bar is
        # admissible, a hair below is not.
        assert rd.payback_hours(bar * 1.001) <= ph
        assert rd.payback_hours(bar * 0.999) > ph


@pytest.mark.parametrize("ph", [0.0, -1.0, -48.0])
def test_a_degenerate_window_publishes_an_unreachable_bar_never_a_free_one(
        monkeypatch, ph):
    """THE FAIL-SAFE DIRECTION OF THE DERIVED BAR, and it is the one direction
    that matters, because `payback_bar_true` exists to be read by OTHER books.

    `RICHDAD_PAYBACK_MAX_H=0` is reachable — it is the same env hatch every
    other setting rides. At a non-positive window the gate admits NOTHING
    (`payback_hours(apr) > 0` for every finite rate), so the honest bar is
    UNREACHABLE. A `0.0` there would publish the exact opposite — "this book
    takes anything" — to `audit_book_overlap`'s cell model and to the daily
    review, on a book that is refusing every coin on the venue. Absence of a
    usable window must never read as absence of a gate ((hs): fail CLOSED in
    the widening direction).

    Driven on BOTH sides so the published number and the gate cannot drift
    apart: the bar is infinite AND the gate really does turn away a coin no
    finite bar could refuse."""
    assert rd.effective_entry_bar(ph) == float("inf"), (
        "a non-positive payback window published a FINITE bar — a reader "
        "would model this book as looser than any real setting while it is "
        "in fact refusing everything")
    blazing = _fund([5.0, 50.0])            # 500% and 5000% TRUE apr
    hot = {c: T0 - 7 * 3600 for c in blazing}
    assert rd.candidates(blazing, set(), hot, T0, max_n=99, payback_max_h=ph,
                         class_ok=lambda c: True) == [], \
        "the gate must admit nothing at a non-positive window"
    # and the ROW carries that, not a number below its own entry floor
    monkeypatch.setattr(rd, "PAYBACK_MAX_H", ph)
    caps = rd.build_extra(
        rd.scan_census({}, set(), {}, T0, class_ok=lambda c: True),
        {}, 0.0, 0.0)["caps"]
    assert caps["payback_bar_true"] > caps["enter_apr"], (
        "the published binding bar dropped BELOW enter_apr — the one thing "
        "this field exists to prevent")


def test_a_shorter_window_demands_a_hotter_coin():
    """The direction the whole change rests on, checked on the two real
    values rather than assumed from the formula."""
    assert rd.effective_entry_bar(SHIPPED_H) > rd.effective_entry_bar(PRIOR_H)
    assert rd.effective_entry_bar(SHIPPED_H) > rd.ENTER_APR, (
        "the literacy gate must TIGHTEN the validated 20% floor, never "
        "widen it — restrict-only is what lets it skip a fresh gate sweep")


def test_one_owner_holds_the_bar_arithmetic():
    """AST, not a substring scan: only the two functions that DEFINE the
    payback relation may name HOURS_PER_YEAR. Anything else recomputing
    `RT * 8760 / window` is a second copy of a rule, and a retyped constant
    is a constant that drifts ((gx)) — this one already lived in three
    places (header, boot line, publish)."""
    owners = {"payback_hours", "effective_entry_bar"}
    offenders = set()
    for fn in ast.walk(_TREE):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if fn.name in owners:
            continue
        for node in ast.walk(fn):
            if isinstance(node, ast.Name) and node.id == "HOURS_PER_YEAR":
                offenders.add(fn.name)
    assert not offenders, (
        f"{sorted(offenders)} recompute the payback bar instead of calling "
        f"effective_entry_bar()")


def test_the_binding_bar_is_published_on_the_row():
    """`enter_apr` reads 0.20 while the payback gate refuses everything below
    ~54.8%, and every cross-book reader (audit_book_overlap's cell model
    included) has only ever seen the 0.20. Publish the constraint that binds
    — an unpublished gate is the (lv) `{open: 0}` ambiguity one layer in."""
    census = rd.scan_census({}, set(), {}, T0, class_ok=lambda c: True)
    caps = rd.build_extra(census, {}, 0.0, 0.0)["caps"]
    assert caps["payback_max_h"] == rd.PAYBACK_MAX_H
    assert caps["payback_bar_true"] == pytest.approx(
        rd.effective_entry_bar(), rel=1e-5)
    assert caps["payback_bar_true"] > caps["enter_apr"], (
        "the published bar must reveal that enter_apr understates this book")


# --- 3. the direction -------------------------------------------------------
def test_the_payback_gate_is_blind_to_the_sign_of_the_funding():
    """THE BOOK TAKES BOTH SIDES — `main()` derives `side = "short" if apr > 0
    else "long"` — so a NEGATIVE TRUE apr is the long side of a
    funding-receiving book, never a rejection. The payback rule is `abs`-based
    for exactly that reason.

    Every other fixture in this module is positive-only, which is how a sign
    bug in the binding gate would ship invisible: it would delete the whole
    LONG side of the book, at 48h exactly as it would have at 120h, while the
    subset and census tests above stayed green. Mirrored pairs, driven through
    the real gate and the real census."""
    fund = {"HOT_S": {"rate": 0.70 / rd.H, "vol": 5e6},
            "HOT_L": {"rate": -0.70 / rd.H, "vol": 5e6},
            "COOL_S": {"rate": 0.25 / rd.H, "vol": 5e6},
            "COOL_L": {"rate": -0.25 / rd.H, "vol": 5e6}}
    hot = {c: T0 - 7 * 3600 for c in fund}
    got = {c for c, _f, _a in rd.candidates(
        fund, set(), hot, T0, max_n=99, class_ok=lambda c: True)}
    assert got == {"HOT_S", "HOT_L"}, (
        f"the shipped gate is not sign-symmetric: admitted {sorted(got)} — "
        f"a receiving position on the long side is the NEGATIVE apr, and "
        f"refusing it halves this book's supply")
    cen = rd.scan_census(fund, set(), hot, T0, class_ok=lambda c: True)
    assert cen["eligible"] == 2 and cen["slow_payback"] == 2, cen


def test_a_tighter_payback_admits_a_strict_subset():
    """RESTRICT-DIRECTION, DRIVEN through the real gate. Everything the
    shipped 48h admits, the old 120h admitted too — so the change can only
    decline, never reach supply the validated sweep never covered (I19).
    `max_n` is deliberately large: a cap would hide a difference behind
    truncation and make the subset claim vacuous."""
    aprs = [0.25, 0.35, 0.45, 0.55, 0.70, 0.90, 1.20]
    fund = _fund(aprs)
    hot = {c: T0 - 7 * 3600 for c in fund}

    def admitted(ph):
        return {c for c, _f, _a in rd.candidates(
            fund, set(), hot, T0, max_n=99, payback_max_h=ph,
            class_ok=lambda c: True)}

    tight, loose = admitted(SHIPPED_H), admitted(PRIOR_H)
    assert tight < loose, (sorted(tight), sorted(loose))
    assert tight and len(loose) == len(fund), (
        "the fixture must span the boundary — all-in or all-out proves "
        "nothing about the direction")
    # and the shipped default IS the tighter of the two, not merely a
    # different number: the module constant reproduces the 48h set.
    assert admitted(None) == tight


def test_what_the_tightening_declines_lands_in_slow_payback():
    """The census mirrors the gate, so the coins the new bar drops must be
    COUNTED as refused-by-literacy, not vanish. `{eligible: 0}` with no
    reason is how a starved book reads identical to an impossible one."""
    aprs = [0.25, 0.35, 0.45, 0.55, 0.70, 0.90, 1.20]
    fund = _fund(aprs)
    hot = {c: T0 - 7 * 3600 for c in fund}
    tight = rd.scan_census(fund, set(), hot, T0, payback_max_h=SHIPPED_H,
                           class_ok=lambda c: True)
    loose = rd.scan_census(fund, set(), hot, T0, payback_max_h=PRIOR_H,
                           class_ok=lambda c: True)
    assert loose["slow_payback"] == 0 and loose["eligible"] == len(fund)
    assert tight["eligible"] == 4 and tight["slow_payback"] == 3, tight
    for cen in (tight, loose):
        assert sum(v for k, v in cen.items() if k != "scanned") \
            == cen["scanned"], cen
    # the delta is a TRANSFER between exactly those two buckets
    assert tight["eligible"] + tight["slow_payback"] == loose["eligible"]


# --- 4. the blast radius ----------------------------------------------------
def test_the_exit_rule_cannot_see_the_payback_knob():
    """AST: `cashflow_exit` must reference neither the window nor the
    function built on it. This is what makes the change ENTRY-ONLY by
    construction rather than by inspection — the (hc) condition for not
    resetting the book's 30-day clock."""
    fn = next(n for n in ast.walk(_TREE)
              if isinstance(n, ast.FunctionDef) and n.name == "cashflow_exit")
    names = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)}
    forbidden = names & {"PAYBACK_MAX_H", "payback_hours",
                         "effective_entry_bar"}
    assert not forbidden, (
        f"cashflow_exit reads {sorted(forbidden)} — an entry-gate change "
        f"would then re-decide positions that are already open")


def test_open_positions_are_untouched_by_the_tightening(monkeypatch):
    """Driven, because the AST pin above proves the knob is not NAMED there
    and not that the verdict is stable. Every position state, every window:
    the exit answer must not move."""
    def pos(side="short", accrued=0.0, fees=0.0, age_h=1.0):
        return {"coin": "ZEC", "side": side, "notional": 80.0,
                "opened_ts": T0 - age_h * 3600, "accrued": accrued,
                "fees": fees}

    cases = [
        # (position, apr) — a pinned coin, a paid decay, a fresh flip, an
        # aged flip, a max-hold, a bleed
        (pos(accrued=0.05), 0.00019),          # ZEC-shaped resting pin
        (pos(accrued=1.0), 0.001),
        (pos(side="short"), -0.5),
        (pos(side="long", accrued=0.2), 0.5),
        (pos(accrued=1.0, age_h=rd.MAX_HOLD_H + 1), 0.5),
        (pos(accrued=-5.0), 0.5),
    ]
    baseline = None
    for ph in (12.0, SHIPPED_H, PRIOR_H, 336.0):
        monkeypatch.setattr(rd, "PAYBACK_MAX_H", ph)
        got = [rd.cashflow_exit(copy.deepcopy(p), apr, T0) for p, apr in cases]
        if baseline is None:
            baseline = got
        assert got == baseline, (ph, got, baseline)
    monkeypatch.undo()
    # the resting-pin case is the one that motivated the change: at 10.5%
    # TRUE it is far above EXIT_APR, so no exit fires and the position rides
    # to max_hold. The tightening keeps it OUT, it does not evict it.
    assert baseline[0] is None
    assert baseline[1] == "decay_paid" and baseline[3] is None
    assert baseline[4] == "max_hold" and baseline[5] == "bleed_stop"


def test_a_held_coin_is_never_re_gated_by_the_new_bar():
    """The other half of entry-only: `candidates` drops a held coin BEFORE
    the payback check, so a coin the tightened bar would refuse today stays
    held rather than becoming a candidate for anything."""
    fund = _fund([0.25])                      # payback 105.1h: refused at 48h
    hot = {c: T0 - 7 * 3600 for c in fund}
    coin = next(iter(fund))
    assert rd.candidates(fund, set(), hot, T0, max_n=99,
                         payback_max_h=SHIPPED_H,
                         class_ok=lambda c: True) == []
    assert rd.candidates(fund, {coin}, hot, T0, max_n=99,
                         payback_max_h=PRIOR_H,
                         class_ok=lambda c: True) == [], \
        "a held coin must be skipped before any economic gate is consulted"


# --- 5. the class screen ----------------------------------------------------
def test_the_crypto_only_code_default_survives_the_service_drift(monkeypatch):
    """The live service carries `RICHDAD_ALLOW_NONCRYPTO=1`, so the row
    publishes `crypto_only: false` while the book is DOCUMENTED crypto-only
    per (lk). Unsetting that env is a Railway act; what the code owes is
    that its own default is unambiguous — an empty/unset var means CRYPTO
    ONLY, and `_class_ok` actually refuses on it."""
    assert _env_default("RICHDAD_ALLOW_NONCRYPTO") == "", (
        "the class screen's env default moved off empty — an opt-OUT that "
        "defaults to on is the (lk) loss re-shipped")
    _reload_with(monkeypatch, "RICHDAD_ALLOW_NONCRYPTO", None)
    assert rd.ALLOW_NONCRYPTO is False

    class _Bus:
        @staticmethod
        def is_crypto(coin):
            return coin != "WTI"

    monkeypatch.setattr(rd, "fleet_bus", _Bus)
    assert rd._class_ok("KAITO") is True
    assert rd._class_ok("WTI") is False, (
        "the screen admitted a non-crypto book at the code default")
    census = rd.scan_census({}, set(), {}, T0)
    assert rd.build_extra(census, {}, 0.0, 0.0)["caps"]["crypto_only"] is True


def test_the_class_screen_is_reversible_and_fails_open(monkeypatch):
    """Both halves of the (lk) contract: the env re-admits without a deploy,
    and a dark `fleet_bus` admits rather than stopping the scan.

    TWO WITNESSES, and the second one is why this test is worth its lines.
    `_class_ok` fails open through TWO independent mechanisms — an explicit
    `fleet_bus is None` short-circuit and a bare `except`. A missing module
    satisfies BOTH (attribute access on None raises, and the except catches
    it), so an absent-bus fixture ALONE cannot witness either of them: a
    mutation round on this file found `except: return False` surviving,
    because the short-circuit was quietly answering for it. The RAISING bus —
    the shape a live outage actually takes, a real module whose lookup throws
    — reaches the except and nothing else."""
    try:
        _reload_with(monkeypatch, "RICHDAD_ALLOW_NONCRYPTO", "1")
        assert rd.ALLOW_NONCRYPTO is True
        assert rd._class_ok("WTI") is True
    finally:
        _reload_with(monkeypatch, "RICHDAD_ALLOW_NONCRYPTO", None)
    assert rd.ALLOW_NONCRYPTO is False

    monkeypatch.setattr(rd, "fleet_bus", None)
    assert rd._class_ok("WTI") is True, (
        "a dark class lookup must never stop a scan (the owner's own "
        "documented direction)")

    class _Angry:
        @staticmethod
        def is_crypto(coin):
            raise RuntimeError("bus payload unreadable")

    monkeypatch.setattr(rd, "fleet_bus", _Angry)
    assert rd._class_ok("KAITO") is True, (
        "a class lookup that RAISES must fail OPEN — a screen that stops the "
        "scan on a bus outage is a book that silently stops trading")
    # and it fails open THROUGH the gate, not merely at the accessor
    fund = {"KAITO": {"rate": 0.70 / rd.H, "vol": 5e6}}
    hot = {"KAITO": T0 - 7 * 3600}
    assert [c for c, _f, _a in
            rd.candidates(fund, set(), hot, T0, max_n=99)] == ["KAITO"]
