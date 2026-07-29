"""Tier 1 — the venue factory: mode selection, fail-safe default, and sizing.

venues/__init__.py decides WHICH VENUE AND WHICH MODE every custom bot runs on —
the shared entry point real-money services boot through — and was 24% covered
with three shipped incidents in its history, none of them pinned:

  * [2026-07-17] the fallback default was hl_paper: a missing/typo'd VENUE on
    ANY service silently landed the shared entry point on Hyperliquid. The fix
    made the default lighter_shadow — right venue AND fail-safe (never live).
  * [2026-07-16 AUDIT FIX] the global LIGHTER_ORDER_USD silently overrode
    per-bot backtested clips on every Lighter mode — Snap Back ran 3x its
    documented size until `own=True` restored per-bot sizing.
  * [2026-07-16 BALANCE] live slot budgets anchored to the LEVER-SCALED clip,
    so a live.clip_scale DOWN-scale (restrict intent) MINTED position slots
    (x0.5 doubled max_open). Slots now anchor to the operator's env clip.

Every venue/broker constructor is stubbed — no network, no signer, no DB.
"""
import math

import pytest

import venues
from venues import VenueContext, venue_context
from venues.safety import SafetyRails

pytestmark = pytest.mark.real_money


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for k in ("VENUE", "LIGHTER_ORDER_USD", "REAL_MONEY_KILL",
              "LIGHTER_MAX_DAILY_LOSS", "MY_BOT_MAX_NOTIONAL"):
        monkeypatch.delenv(k, raising=False)
    # Boot-gate refusals publish to the DB-backed store; neutralize (the
    # test_safety_rails pattern) so no test depends on Postgres.
    monkeypatch.setattr(SafetyRails, "_publish_refusal", lambda self, why: None)


class _FakeVenue:
    """Records constructor kwargs; satisfies what VenueContext touches."""
    name = "fake"

    def __init__(self, *a, **kw):
        self.args, self.kw = a, kw

    def supports(self, coin):
        return True


class _FakeBroker:
    def __init__(self, *a, **kw):
        self.args, self.kw = a, kw


def _stub_constructors(monkeypatch):
    """Swap every heavy constructor for a recorder; return the recorders' logs."""
    made = {"lighter": [], "shadow": [], "hl": [], "paper": []}

    import venues.lighter_client as lc
    import venues.shadow as sh
    import venues.hyperliquid_client as hc
    import paper_broker as pb

    def _mk(log):
        class _C:
            def __new__(cls, *a, **kw):
                obj = _FakeVenue(*a, **kw)
                log.append(obj)
                return obj
        return _C

    monkeypatch.setattr(lc, "LighterClient", _mk(made["lighter"]))
    monkeypatch.setattr(sh, "ShadowBroker", _mk(made["shadow"]))
    monkeypatch.setattr(hc, "HyperliquidClient", _mk(made["hl"]))
    monkeypatch.setattr(pb, "PaperBroker", _mk(made["paper"]))
    return made


# ── mode selection: the fail-safe default ────────────────────────────────────
def test_unset_venue_defaults_to_lighter_shadow_never_live(monkeypatch):
    made = _stub_constructors(monkeypatch)
    ctx = venue_context("my-bot")
    assert ctx.mode == "lighter_shadow"
    assert ctx.dry_run is True and ctx.broker is not None
    # the shadow client must be signer-LESS: a config slip can never put real
    # money on the book (the 17-Jul operator rule, both halves)
    assert made["lighter"][0].kw.get("with_signer") is False
    assert not made["hl"], "default must be Lighter, not Hyperliquid"


def test_empty_venue_string_also_falls_back_to_shadow(monkeypatch):
    _stub_constructors(monkeypatch)
    monkeypatch.setenv("VENUE", "   ")
    assert venue_context("my-bot").mode == "lighter_shadow"


def test_unknown_venue_refuses_to_boot(monkeypatch):
    _stub_constructors(monkeypatch)
    monkeypatch.setenv("VENUE", "lighter_livee")   # the typo class
    with pytest.raises(SystemExit):
        venue_context("my-bot")


def test_bot_id_suffix_per_mode(monkeypatch):
    made = _stub_constructors(monkeypatch)
    monkeypatch.setenv("VENUE", "lighter_shadow")
    ctx = venue_context("my-bot")
    assert ctx.bot_id == "my-bot-lshadow"
    # ShadowBroker is keyed by the SUFFIXED id — shadow curves must never
    # contaminate the paper-era rows
    assert made["shadow"][0].args[0] == "my-bot-lshadow"

    monkeypatch.setenv("VENUE", "hl_paper")
    assert venue_context("my-bot").bot_id == "my-bot"   # paper era: bare


def test_live_mode_wires_signer_guard_and_no_local_broker(monkeypatch):
    made = _stub_constructors(monkeypatch)
    monkeypatch.setenv("VENUE", "lighter_live")
    monkeypatch.setenv("REAL_MONEY_KILL", "DISARMED_I_UNDERSTAND")
    monkeypatch.setenv("MY_BOT_MAX_NOTIONAL", "150")
    ctx = venue_context("my-bot")
    assert ctx.mode == "lighter_live" and ctx.bot_id == "my-bot-lighter"
    assert ctx.broker is None and ctx.dry_run is False
    kw = made["lighter"][0].kw
    assert kw.get("with_signer") is True
    assert kw.get("net") == "mainnet"
    # equity-guard state persists under the SUFFIXED id (redeploy cannot
    # re-anchor validation on a dislocated print)
    assert kw.get("guard_state_key") == "my-bot-lighter:eqguard"


def test_testnet_mode_uses_testnet_not_mainnet(monkeypatch):
    made = _stub_constructors(monkeypatch)
    monkeypatch.setenv("VENUE", "lighter_testnet")
    ctx = venue_context("my-bot")
    assert made["lighter"][0].kw.get("net") == "testnet"
    assert ctx.bot_id == "my-bot-ltest" and ctx.dry_run is False


def test_live_boot_gate_still_bites_through_the_factory(monkeypatch):
    # venue_context must not soften SafetyRails: live with no cap refuses.
    _stub_constructors(monkeypatch)
    monkeypatch.setenv("VENUE", "lighter_live")
    monkeypatch.setenv("REAL_MONEY_KILL", "DISARMED_I_UNDERSTAND")
    with pytest.raises(SystemExit):
        venue_context("my-bot")


def test_failed_live_auth_publishes_an_error_row_and_reraises(monkeypatch):
    # [2026-07-10] a live bot that can't authenticate must die LOUDLY: an
    # explicit error row under the suffixed id, then the real exception.
    import venues.lighter_client as lc

    def _boom(*a, **kw):
        raise ValueError("private key does not match")

    monkeypatch.setattr(lc, "LighterClient", _boom)
    published = {}
    import bot_pnl_store
    monkeypatch.setattr(bot_pnl_store, "publish",
                        lambda bot, **kw: published.update({"bot": bot, **kw}) or True)
    monkeypatch.setenv("VENUE", "lighter_live")
    monkeypatch.setenv("REAL_MONEY_KILL", "DISARMED_I_UNDERSTAND")
    monkeypatch.setenv("MY_BOT_MAX_NOTIONAL", "150")
    with pytest.raises(ValueError):
        venue_context("my-bot")
    assert published["bot"] == "my-bot-lighter"
    assert published["status"] == "error"
    assert "private key" in published["extra"]["error"]


# ── VenueContext sizing: order_usd / max_open_positions ──────────────────────
def _ctx(mode, cap=None, broker=None):
    rails = SafetyRails("my-bot", mode)
    if cap is not None:
        rails.max_notional = float(cap)
    return VenueContext(mode, _FakeVenue(), broker, "my-bot", rails)


def test_order_usd_hl_paper_keeps_the_bots_own_constant():
    assert _ctx("hl_paper", broker=_FakeBroker()).order_usd(17.0) == 17.0


def test_order_usd_lighter_modes_read_the_env_anchor(monkeypatch):
    monkeypatch.setenv("LIGHTER_ORDER_USD", "25")
    assert _ctx("lighter_shadow", broker=_FakeBroker()).order_usd(99.0) == 25.0
    monkeypatch.delenv("LIGHTER_ORDER_USD")
    assert _ctx("lighter_shadow", broker=_FakeBroker()).order_usd(99.0) == 30.0


def test_order_usd_own_clip_survives_the_global_anchor(monkeypatch):
    # [2026-07-16 AUDIT FIX] Snap Back's $10 backtested clip ran at $30 (3x)
    # because the global env overrode it on every Lighter mode. own=True keeps
    # the bot's documented size on every non-live mode…
    monkeypatch.setenv("LIGHTER_ORDER_USD", "30")
    assert _ctx("lighter_shadow", broker=_FakeBroker()).order_usd(10.0, own=True) == 10.0
    # …while LIVE deliberately keeps the operator's anchor + lever chain.
    assert _ctx("lighter_live").order_usd(10.0, own=True) == 30.0


def test_order_usd_live_applies_the_bounded_clip_lever(monkeypatch):
    class _T:
        def get_lever(self, key, default):
            assert key == "live.clip_scale"
            return 1.25
    monkeypatch.setattr(venues, "_tuning", _T())
    assert _ctx("lighter_live").order_usd(99.0) == 37.5      # 30 * 1.25
    # shadow modes never consume the LIVE lane's lever
    assert _ctx("lighter_shadow", broker=_FakeBroker()).order_usd(99.0) == 30.0


def test_order_usd_dark_tuning_organ_is_neutral(monkeypatch):
    monkeypatch.setattr(venues, "_tuning", None)
    assert _ctx("lighter_live").order_usd(99.0) == 30.0


def test_max_open_hl_paper_and_capless_keep_the_paper_default():
    assert _ctx("hl_paper", broker=_FakeBroker()).max_open_positions(4) == 4
    assert _ctx("lighter_shadow", broker=_FakeBroker()).max_open_positions(4) == 4


def test_max_open_live_slots_anchor_to_env_not_the_lever(monkeypatch):
    # [2026-07-16 BALANCE] the slot-minting regression: a restrict-intent
    # x0.5 clip lever must NOT double max_open. Slots anchor to the env clip.
    class _T:
        def get_lever(self, key, default):
            return 0.5
    monkeypatch.setattr(venues, "_tuning", _T())
    ctx = _ctx("lighter_live", cap=150)
    assert ctx.order_usd(99.0) == 15.0                    # lever DOES reshape the clip
    assert ctx.max_open_positions(4) == 5                 # floor(150/30) — env anchor
    # and an up-scale must not BURN slots either
    class _T2:
        def get_lever(self, key, default):
            return 1.5
    monkeypatch.setattr(venues, "_tuning", _T2())
    assert _ctx("lighter_live", cap=150).max_open_positions(4) == 5


def test_max_open_shadow_mirrors_its_own_clip(monkeypatch):
    monkeypatch.setenv("LIGHTER_ORDER_USD", "25")
    ctx = _ctx("lighter_shadow", cap=100, broker=_FakeBroker())
    assert ctx.max_open_positions(9) == math.floor(100 / 25)


def test_max_open_floors_at_one():
    assert _ctx("lighter_live", cap=10).max_open_positions(4) == 1
