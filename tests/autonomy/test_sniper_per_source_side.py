"""🎯 The sniper's side is PER SOURCE — and the fade that made it so.

Operator, 26-Aug: *"let listing sniper fly like it used to."*

It used to fly as `listing_sniper.py`, sniping SPOT listings across ~100 CEXes,
where a fresh listing is a buying event and LONG is the trade. This book snipes
PERP listings on ONE venue, and a perp lists AFTER the spot hype. Measured on
the venue's own tape those are opposite trades, and the successor inherited the
predecessor's side.

MEASURED (45 venue-priced books, every hour of each book's own first 21 days,
n=23,102), LONG: 0-7d -0.125%/6h (t=-2.47) and 8-21d -0.083%/6h (t=-2.70); at
24h -0.317% and -0.436% (t=-7.47). By 22-40d the fade is gone; by 41-60d it
reverses. The falling-tape objection (item 18) is answered by a control PAIRED
WITHIN COIN: the identical bracket on the SAME 45 coins at ages 61-120d returns
-0.022%/-0.048%/+0.080% at 6h/24h/72h, every t below 1.0. The mature control is
flat, so this is an age effect and not beta.

These tests pin the SHAPE of the fix, never the numbers: a study's numbers move
with the tape, but "the side comes from the source, and an unknown source
degrades to the old behaviour" must hold whatever the tape says.
"""
import ast
import importlib
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]


@pytest.fixture()
def sniper(monkeypatch):
    monkeypatch.delenv("SNIPER_DIRECTION", raising=False)
    for s in ("LISTING", "SURGE", "YOUNG"):
        monkeypatch.delenv(f"SNIPER_SIDE_{s}", raising=False)
        monkeypatch.delenv(f"SNIPER_HOLD_H_{s}", raising=False)
    import lighter_perp_sniper as m
    return importlib.reload(m)


# ------------------------------------------------------- the measured change
def test_the_two_debut_sources_are_short_and_surge_is_not(sniper):
    """`listing` and `young` target the faded 0-21d band; `surge` is a volume
    event on a mostly-MATURE book, whose control measured FLAT. Flipping surge
    too would be applying one source's evidence to another's cell — the exact
    (lk) error this book has already paid for once."""
    assert sniper.side_is_long("listing") is False
    assert sniper.side_is_long("young") is False
    assert sniper.side_is_long("surge") is True


def test_an_unknown_source_degrades_to_the_old_behaviour_never_a_guess(sniper):
    """(ht): unknown degrades to the previous, honest value. A position with no
    recorded source — including one restored from a state blob written before
    this shipped — must not be assigned a side by inference."""
    for unknown in (None, "", "junk", 0, object()):
        assert sniper.side_is_long(unknown) is sniper.DIRECTION_LONG
        assert sniper.hold_sec_for(unknown) == float(sniper.MAX_HOLD_SEC)


def test_a_pinned_direction_overrides_every_source(monkeypatch):
    """The one-env revert. `SNIPER_DIRECTION=long` returns the book to
    single-sided without touching code."""
    monkeypatch.setenv("SNIPER_DIRECTION", "long")
    import lighter_perp_sniper as m
    m = importlib.reload(m)
    assert m.DIRECTION_PINNED is True
    assert all(m.side_is_long(s) is True for s in m.SNIPE_SOURCES)
    monkeypatch.setenv("SNIPER_DIRECTION", "short")
    m = importlib.reload(m)
    assert all(m.side_is_long(s) is False for s in m.SNIPE_SOURCES)


def test_one_source_moves_by_env_without_moving_the_others(monkeypatch):
    monkeypatch.delenv("SNIPER_DIRECTION", raising=False)
    monkeypatch.setenv("SNIPER_SIDE_YOUNG", "long")
    import lighter_perp_sniper as m
    m = importlib.reload(m)
    assert m.side_is_long("young") is True
    assert m.side_is_long("listing") is False, "one lever must move one source"


# --------------------------------------------------------------- the HOLD
def test_the_debut_sources_hold_longer_than_the_surge_source(sniper):
    """6h on the fade is +0.132% = 13bps gross, inside plausible round-trip
    slippage at this book's volume floor; 24h is 67bps and clears it."""
    assert sniper.hold_sec_for("young") == 24 * 3600
    assert sniper.hold_sec_for("listing") == 24 * 3600
    assert sniper.hold_sec_for("surge") == float(sniper.MAX_HOLD_SEC)


def test_the_hold_is_not_the_grid_edge(sniper):
    """72h measured BEST (+1.690%, by-coin t=+4.51) and is deliberately NOT
    taken: it is the EDGE of the tested grid, and (hl)/(sk) is explicit that a
    grid-edge winner is reported unbounded, never shipped as a value. 24h is
    the interior — the 🧭 nav-cook precedent."""
    assert max(sniper.SOURCE_HOLD_H.values()) <= 24.0, sniper.SOURCE_HOLD_H


def test_the_exit_timer_reads_the_positions_own_hold_not_the_constant():
    """A source-tagged position must time out on ITS OWN clock. The timer used
    `MAX_HOLD_SEC` directly, so a 24h source would have been closed at 6h."""
    src = (ROOT / "lighter_perp_sniper.py").read_text()
    assert "held_sec >= hold_sec_for(entry_src.get(coin))" in src, \
        "the max-hold branch must resolve the hold per position"
    assert "held_sec >= MAX_HOLD_SEC" not in src, \
        "a second, constant timer would silently win for one of the sources"


# ------------------------------------------------- the payload must not lie
def test_the_held_map_reads_the_side_off_the_position(sniper):
    """With one side per source, a `held` map built from a module constant
    reports every short as a long — to `fleet_risk`'s exposure view, which is
    the organ that decides whether the fleet is one-sided."""
    src = (ROOT / "lighter_perp_sniper.py").read_text()
    tree = ast.parse(src)
    found = False
    for node in ast.walk(tree):
        if isinstance(node, ast.DictComp):
            blob = ast.unparse(node)
            if '"L"' in blob or "'L'" in blob:
                found = True
                assert "side_is_long" in blob, (
                    "the held map must resolve each position's OWN side; "
                    f"got: {blob}")
    assert found, "no held-map comprehension found to check"


def test_the_payload_publishes_a_side_per_source(sniper):
    """A single `dir` scalar cannot describe a two-sided book. It stays for
    older readers; the map beside it is the real answer."""
    src = (ROOT / "lighter_perp_sniper.py").read_text()
    for key in ('"dir_by_src"', '"hold_h_by_src"', '"dir_pinned"'):
        assert key in src, f"{key} must reach the published payload"


# ------------------------------------------------------------- the supply
def test_the_young_volume_floor_stays_above_the_slippage_models_step(sniper):
    """0.25 -> 0.20 admits ANSEM ($0.228M/day), the only venue-priced book in
    120 days the old floor refused while having real turnover. It stays at
    TWICE the $0.1M step where the fleet's slippage model changes tier —
    which is exactly why (ty) REFUSED $0.10M, and that refusal is unchanged."""
    assert sniper.YOUNG_MIN_VOL_M == pytest.approx(0.20)
    assert sniper.YOUNG_MIN_VOL_M >= 0.20, \
        "below 0.2 the slippage model cannot price the band this would admit"


def test_the_young_window_was_not_widened(sniper):
    """The obvious move, refused by the tape: the fade is gone by 22-40d
    (-0.094%/24h) and reverses by 41-60d, so a wider window buys supply by
    diluting the very effect being traded."""
    assert sniper.YOUNG_MAX_BARS == 21
