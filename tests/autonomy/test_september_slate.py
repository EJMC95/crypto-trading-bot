"""[2026-09-02] THE SEPTEMBER SLATE — five I17 calls made in one delegated
operator act (Eamon: "I give you permission to fix the above"), each on the
grader's own CURRENT verdict, read live before shipping:

    🛢️ garrett        unreachable  upper bound −0.455% ≤ 0 (n=85)
    🧘 douglas        unreachable  ub −0.357% ≤ 0 (n=81)
    💸 farmer shadow  unreachable  ub −0.231% ≤ 0 (n=200+)
    🧭 nav-cook       unreachable  ub −0.020% ≤ 0 (n=38)
    📐 grimes         no_rate      0 closes ever; gate open 0/31 retests

🔮 georgia v1 was on the slate and is DEFERRED, not retired — her cap-5
trajectory carries a pre-registered prediction (claims_ledger
`georgia-entry-cap-5-days-to-gate`, grade_after 10-Sep) and retiring her
before its read voids a registered prediction (I21/I25). Pinned here so a
"tidy-up" cannot silently retire her early OR silently drop the deferral.

What this file pins, per the (nf)/(mr) precedents:
  * every retired row is in BOTH halves (RETIRED_ROWS hides, LEGACY_BOTS
    prunes) — doing one hides your own omission;
  * each module's guard exists, keys on the right thing, and respects its
    override env (mutation-verified by editing the env at runtime);
  * the funding guard is ROW-scoped by RESOLVED id — the garrett variant and
    the farmer shadow idle, an unlisted variant does not, and the LIVE arm's
    (ta) mechanism is untouched;
  * georgia v1 is NOT retired and her v3 row is NOT retired.
"""
import os
import sys

import pytest

pytestmark = pytest.mark.autonomy

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

SLATE = [
    "band-garrett-lshadow",
    "book-douglas-lshadow",
    "perps-funding-lighter-lshadow",
    "nav-cook-lshadow",
    "book-grimes-lshadow",
]


def test_every_slate_row_is_in_both_halves():
    import pnl_dashboard as pd
    import cleanup_legacy_bots as clb
    for row in SLATE:
        assert row in pd.RETIRED_ROWS, f"{row} not hidden (RETIRED_ROWS)"
        assert row in clb.LEGACY_BOTS, f"{row} not pruned (LEGACY_BOTS)"


def test_georgia_is_deferred_not_retired():
    """Both directions: she must not be swept into the slate early, and the
    deferral must not quietly become a retirement without the 10-Sep read."""
    import pnl_dashboard as pd
    import cleanup_legacy_bots as clb
    import lighter_family_bot as fam
    for row in ("freqtrade-georgia-lshadow", "freqtrade-georgia-v3-lshadow"):
        assert row not in pd.RETIRED_ROWS, f"{row} hidden — the deferral says 10-Sep"
        assert row not in clb.LEGACY_BOTS, f"{row} pruned — same"
    assert "freqtrade-georgia" not in fam.RETIRED_BOOKS
    assert "freqtrade-georgia-v3" not in fam.RETIRED_BOOKS
    # ...and the pre-registered read the deferral rests on still exists
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import claims_ledger as cl
    row = next(c for c in cl.CLAIMS
               if c["id"] == "georgia-entry-cap-5-days-to-gate")
    assert row["grade_after"] == "2026-09-10", row["grade_after"]


def test_the_funding_guard_is_row_scoped_and_override_respected(monkeypatch):
    import lighter_funding_bot as fb
    assert set(fb.RETIRED_SHADOW_BOOKS) == {"perps-funding-lighter-lshadow",
                                            "band-garrett-lshadow"}
    monkeypatch.delenv("FARMER_SHADOW_RETIRED_OVERRIDE", raising=False)
    monkeypatch.delenv("GARRETT_RETIRED_OVERRIDE", raising=False)
    assert fb.shadow_book_retired("perps-funding-lighter-lshadow")
    assert fb.shadow_book_retired("band-garrett-lshadow")
    # ROW scope: the live arm and an unlisted variant are untouched
    assert not fb.shadow_book_retired("perps-funding-lighter")
    assert not fb.shadow_book_retired("band-future-lshadow")
    # the override resurrects exactly one book, not the map
    monkeypatch.setenv("GARRETT_RETIRED_OVERRIDE", "run")
    assert not fb.shadow_book_retired("band-garrett-lshadow")
    assert fb.shadow_book_retired("perps-funding-lighter-lshadow")


def test_the_live_arm_mechanism_is_untouched():
    """The (ta) retirement of the REAL-MONEY arm lives in
    fleet_bus.RETIRED_LIVE_ARMS and FLATTENS; the slate's shadow guard idles.
    They must stay different mechanisms — a shadow idle loop beside real
    positions would leave them unmanaged."""
    import lighter_funding_bot as fb
    import fleet_bus
    assert "perps-funding-lighter" not in fb.RETIRED_SHADOW_BOOKS
    assert "perps-funding-lighter-lighter" in fleet_bus.RETIRED_LIVE_ARMS


class _Idled(Exception):
    """Raised by the trapped sleep — proof main() reached the idle loop."""


def test_the_douglas_guard_spares_his_variant_tenant(monkeypatch):
    """[2026-09-02, ~3h after the slate] 🚀 book-bezos runs THIS engine —
    `core.main()` after reassigning `core.BOT` — and the guard's first,
    process-scoped version idled him for ~3h behind a banner naming douglas,
    which no `bezos` log filter could match. The (mr) idle-the-whole-process
    trap, walked into by the entry citing it. The guard now keys on the
    module-level BOT; this drives the VARIANT path and demands it get past
    the guard (venue_context trapped = success; the idle = the regression).
    Grep a module's importers before choosing retirement scope."""
    import importlib
    m = importlib.import_module("lighter_book_douglas_bot")
    monkeypatch.delenv("DOUGLAS_RETIRED_OVERRIDE", raising=False)
    monkeypatch.setattr(m, "BOT", "book-bezos")
    monkeypatch.setattr(m.time, "sleep",
                        lambda _s: (_ for _ in ()).throw(_Idled()))

    class _PastTheGuard(Exception):
        pass

    monkeypatch.setattr(m, "venue_context",
                        lambda *a, **k: (_ for _ in ()).throw(_PastTheGuard()))
    monkeypatch.setattr(sys, "argv", ["lighter_book_bezos_bot"])
    try:
        m.main()
        pytest.fail("main returned without reaching venue_context")
    except _PastTheGuard:
        pass
    except _Idled:
        pytest.fail("the douglas guard idled his VARIANT — it has gone "
                    "process-scoped again; scope it to BOT == 'book-douglas'")


@pytest.mark.parametrize("mod,env,marker", [
    ("lighter_book_douglas_bot", "DOUGLAS_RETIRED_OVERRIDE", "-0.357%"),
    ("lighter_book_grimes_bot", "GRIMES_RETIRED_OVERRIDE", "0 of 31"),
    ("lighter_nav_cook_bot", "COOK_RETIRED_OVERRIDE", "-0.020%"),
])
def test_each_module_guard_actually_idles(mod, env, marker, monkeypatch,
                                          capsys):
    """DRIVEN, not grepped — a substring pin survives a renamed env or an
    inverted condition (measured: the first mutation round's rename passed a
    source-level version of this test). main() is called with the override
    unset and `time.sleep` trapped: reaching the trap proves the guard fired
    BEFORE any venue call; the printed reason must carry the measured number
    (I23: the reason is the record); and with the override set, main must NOT
    idle at the guard (it is allowed to fail later, offline — anything but
    _Idled)."""
    import importlib
    m = importlib.import_module(mod)
    monkeypatch.delenv(env, raising=False)
    monkeypatch.setattr(m.time, "sleep",
                        lambda _s: (_ for _ in ()).throw(_Idled()))
    monkeypatch.setattr(sys, "argv", [mod])
    with pytest.raises(_Idled):
        m.main()
    out = capsys.readouterr().out
    assert "RETIRED" in out and marker in out, (
        f"{mod}: the guard's reason lost its measured number ({marker})")
    # the override resurrects: with venue_context trapped, reaching IT (and
    # not the idle) proves the guard lifted — deterministic and offline, no
    # real venue call, no dependence on what a live loop does next.
    class _PastTheGuard(Exception):
        pass

    monkeypatch.setenv(env, "run")
    monkeypatch.setattr(m, "venue_context",
                        lambda *a, **k: (_ for _ in ()).throw(_PastTheGuard()))
    try:
        m.main()
        pytest.fail(f"{mod}: main returned without reaching venue_context")
    except _PastTheGuard:
        pass                                    # got past the guard — correct
    except _Idled:
        pytest.fail(f"{mod}: {env}=run did not lift the idle guard")
