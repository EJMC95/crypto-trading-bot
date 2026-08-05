"""[2026-08-06 (kl)] 🎸 BARNESY'S ONLY WORKING SLEEVE HAD NO VALIDATED CORE.

`(ki)` NAMED this in its own source comment and fixed only half of it:

    "Unlike its parent ⚖️ Counterweight — which starts from a VALIDATED
     30-name crypto core and only tops up from the scout — this sleeve had
     NO core at all: scout_universe(min_vol_m=1.0, limit=60) ranked by
     volume, full stop."

The other half is the CORE and the WIDTH. Both of the parent's validations
cleared K=5 over a 30-name hand list (the HL lab and the 31-Jul (ia) Lighter
re-run: +13.7%, maxDD 9.6%). `(jg)` reverted the parent 60 -> 30 on that
widening's OWN pre-registered criterion — in-era t=-0.44 and FALLING from a
0.65 baseline, mean -0.361%/trade, -$16.01 MTM, fleet-worst — **eight hours
before this book was born**, and the child shipped the reverted half anyway.

With zero closes this costs nothing today. After `BARNES_FREEZE_UNTIL`
(4-Sep) it costs the whole 30-day sample ((hm)), which is why it is now.

WHY A SECOND COPY OF THE RULE EXISTS, and how it is kept honest: the parent's
`resolve_universe` is not in Barnesy's image, and dragging a whole bot module
in to reuse six lines is the born-dark trade this fleet keeps losing. So the
two implementations are pinned EQUAL by the check below rather than shared.
"""
import pathlib
import sys

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

import fleet_bus  # noqa: E402
import lighter_band_barnes_bot as barnes  # noqa: E402
import lighter_funding_spread_bot as parent  # noqa: E402


@pytest.fixture
def scout(monkeypatch):
    """A scout list containing crypto AND the tokenised equities that made
    `(ki)` necessary, so the top-up screen is exercised, not assumed."""
    syms = ["BTC", "ETH", "AAPL", "PEPE", "TENCENT", "ARKM",
            "US500", "WEN", "MOODENG", "OPENAI", "SPY", "ZEC"]
    monkeypatch.setattr(fleet_bus, "scout_universe",
                        lambda **kw: list(syms))
    monkeypatch.setattr(fleet_bus, "is_crypto",
                        lambda s, current_time=None: s.upper() not in {
                            "AAPL", "TENCENT", "US500", "WEN", "OPENAI", "SPY"})
    return syms


class TestItMatchesTheParentTermForTerm:
    """The duplicated rule, held honest by an executable equality check."""

    @pytest.mark.parametrize("core,width", [
        (["BTC", "ETH", "SOL"], 8),        # top-up path
        (["BTC", "ETH", "SOL"], 3),        # core already fills the width
        (["BTC", "ETH", "SOL"], 0),        # widening disabled
        (["ZEC"], 6),
    ])
    def test_same_inputs_same_universe(self, monkeypatch, scout, core, width):
        monkeypatch.setattr(barnes, "XSECT_CORE", list(core))
        monkeypatch.setattr(barnes, "XSECT_UNIVERSE_N", width)
        monkeypatch.setattr(barnes, "XSECT_MIN_VOL_M", 1.0)
        assert barnes.resolve_xsect_universe({}) == \
            parent.resolve_universe(core, width, 1.0)


class TestTheCoreIsSacred:
    def test_core_names_are_never_dropped(self, monkeypatch, scout):
        """The parent's contract: they are the backtested list, and dropping
        one silently changes what the book IS."""
        monkeypatch.setattr(barnes, "XSECT_CORE", ["BTC", "ETH", "SOL"])
        monkeypatch.setattr(barnes, "XSECT_UNIVERSE_N", 30)
        out = barnes.resolve_xsect_universe({})
        assert out[:3] == ["BTC", "ETH", "SOL"]

    def test_only_the_topup_is_crypto_screened(self, monkeypatch, scout):
        """A core containing a non-crypto name survives; the scout's
        additions do not. Same asymmetry the parent ships."""
        monkeypatch.setattr(barnes, "XSECT_CORE", ["BTC", "SPY"])
        monkeypatch.setattr(barnes, "XSECT_UNIVERSE_N", 10)
        out = barnes.resolve_xsect_universe({})
        assert "SPY" in out, "a CONFIGURED name must never be filtered"
        for leaked in ("AAPL", "TENCENT", "WEN", "OPENAI", "US500"):
            assert leaked not in out, leaked


class TestTheShippedConfigIsTheValidatedOne:
    def test_width_matches_the_core_so_nothing_tops_up(self):
        """30 names, width 30 — the parent's post-(jg) shape exactly: the
        widening is INERT and the book ranks the validated list."""
        assert barnes.XSECT_UNIVERSE_N == 30
        assert len(barnes.XSECT_CORE) == 30

    def test_the_core_is_the_parents_validated_list(self):
        assert [c.strip().upper() for c in barnes.XSECT_CORE] == \
               [c.strip().upper() for c in parent.COINS]

    def test_k_is_still_the_validated_plateau_centre(self):
        assert barnes.K == parent.K == 5


class TestFailSafe:
    def test_a_dark_scout_returns_the_core_unchanged(self, monkeypatch):
        monkeypatch.setattr(fleet_bus, "scout_universe", lambda **kw: [])
        monkeypatch.setattr(barnes, "XSECT_CORE", ["BTC", "ETH"])
        monkeypatch.setattr(barnes, "XSECT_UNIVERSE_N", 30)
        assert barnes.resolve_xsect_universe({}) == ["BTC", "ETH"]

    def test_a_raising_scout_never_stops_the_book(self, monkeypatch):
        def boom(**kw):
            raise RuntimeError("bus down")
        monkeypatch.setattr(fleet_bus, "scout_universe", boom)
        monkeypatch.setattr(barnes, "XSECT_CORE", ["BTC", "ETH"])
        out = barnes.resolve_xsect_universe({})
        assert out[:2] == ["BTC", "ETH"]

    def test_the_venue_direct_fallback_still_screens(self, monkeypatch):
        """A dark scout AND a core short of the width: the venue-direct path
        is the second way into the same rank and must be screened too."""
        monkeypatch.setattr(fleet_bus, "scout_universe", lambda **kw: [])
        monkeypatch.setattr(fleet_bus, "is_crypto",
                            lambda s, current_time=None: s.upper() != "SPY")
        monkeypatch.setattr(barnes, "XSECT_CORE", ["BTC"])
        monkeypatch.setattr(barnes, "XSECT_UNIVERSE_N", 10)
        fund = {"SPY": {"vol": 9e6}, "ZEC": {"vol": 9e6}}
        out = barnes.resolve_xsect_universe(fund)
        assert "ZEC" in out and "SPY" not in out


class TestTheBindingGatesAreReachable:
    """I18: Barnesy had three registered levers, all tighten-only or inert on
    a starved sleeve, while every gate its own census names as binding was a
    bare literal. Registering them is REACH, not payoff — the defaults do not
    move, and `(it)` already recorded that walking `carry.min_vol` to its
    floor unlocked zero books."""

    LEVERS = ("barnes.persist_h", "barnes.carry_min_vol",
              "barnes.extreme_min_vol", "barnes.xsect_universe_n")

    @pytest.mark.parametrize("lever", LEVERS)
    def test_registered_and_caged(self, lever):
        import fleet_tuning as ft
        assert lever in ft.LEVERS, f"{lever} is still a bare literal"
        spec = ft.LEVERS[lever]
        assert spec["lo"] < spec["hi"], "a degenerate cage is not a cage"
        assert spec["lo"] <= spec["env_default"] <= spec["hi"]

    @pytest.mark.parametrize("lever", LEVERS)
    def test_consumed_by_apply_tuning(self, lever):
        """A registered lever with no reader is the inert failure (gu) exists
        to prevent — and `_ENV_DEFAULTS` must carry it, or the KeyError is
        swallowed and the lever silently never moves."""
        import ast
        src = (_ROOT / "lighter_band_barnes_bot.py").read_text()
        assert lever in src, lever
        tree = ast.parse(src)
        fn = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == "apply_tuning")
        assert lever in ast.dump(fn), f"{lever} registered but not consumed"

    def test_every_consumed_attr_has_an_env_default(self):
        for attr in ("PERSIST_H", "CARRY_MIN_VOL", "EXTREME_MIN_VOL",
                     "XSECT_UNIVERSE_N"):
            assert attr in barnes._ENV_DEFAULTS, attr

    def test_the_freeze_still_refuses_all_of_them(self):
        """Reach is granted, the birth freeze is NOT lifted: the rail still
        moves nothing until BARNES_FREEZE_UNTIL."""
        frozen = barnes._freeze_until_ts() - 86400.0
        assert barnes.freeze_active(frozen)
        assert barnes.apply_tuning(frozen) == {}
