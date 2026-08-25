#!/usr/bin/env python3
"""[2026-08-22 (sx)] THE LIVE RUNNER IS A VARIANT HOST, AND 🙏 AVO MUST NOT MOVE.

**Eamon, 22-Aug: "get georgia ready to go live on a new sub account ill deposit
into later today prepared for 5x leverage".**

🔮 georgia gets a live arm as a VARIANT of the proven module rather than a
1,800-line copy — the 🛢️ Garrett rule ((lp)): one machine, every success
instrument inherited free (claim_writer + standby, the latched daily halt, the
capital-adjust equity guard, the venue-truth reconciler, the notional cap and
`cap_slots` census, `diversified_order`, the (st) scan census, the MTM equity
series, real-fill telemetry, the per-asset regime gate, the brain's
restrict-only sizing). A copy would have to re-earn all of it and would drift.

**THE SAFETY PROPERTY OF THIS CHANGE IS THAT AVO DOES NOT MOVE**, and it is a
real-money book, so most of this file is about that rather than about georgia.
Tests 1-3 pin the default path name by name.

The dangerous failure this forbids (test 4): an unknown or typo'd
`FAMILY_LIVE_BOOK` degrading to Avo. georgia's service would then publish to
Avo's row, restore Avo's state key, and manage Avo's REAL POSITIONS. Refusing
at import is the only acceptable behaviour — I8's "unknown never degrades to a
guess", where the guess would be another book's money.

Test 6 is the number Eamon asked about: 5x means something DIFFERENT on
georgia, because her stop is half as wide.
"""
import contextlib
import importlib
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


@contextlib.contextmanager
def loaded(book=None, **env):
    """Import the live runner as `book` with `env` applied, and put the module
    back on the way out.

    A CONTEXT MANAGER rather than a function returning the module, which is how
    the first draft of this file was written and why every one of its
    assertions passed against the WRONG module: restoring the environment
    requires a second `reload`, and doing that in a `finally` before returning
    handed the caller a module that had already been reset to the defaults. The
    tests still went green on Avo — the only book whose values happen to be the
    defaults — which is exactly the shape that would have let a georgia
    regression through."""
    saved = dict(os.environ)
    os.environ.pop("FAMILY_LIVE_BOOK", None)
    if book:
        os.environ["FAMILY_LIVE_BOOK"] = book
    for k, v in env.items():
        os.environ[k] = v
    import lighter_avo_live_bot as m
    try:
        yield importlib.reload(m)
    finally:
        os.environ.clear()
        os.environ.update(saved)
        importlib.reload(m)


# ---- 1-3  🙏 Avo does not move -------------------------------------------

def test_the_default_is_avo_unchanged():
    with loaded() as m:
        assert m.BOT == "freqtrade-avo-maria"
        assert m.BOT_ROW == "freqtrade-avo-maria-lighter"
        assert m.SHADOW_ROW == "freqtrade-avo-maria-lshadow"
        assert m.STATE_KEY == "freqtrade-avo-maria-lighter:live"
        assert m._PFX == "AVO"
        assert m.LIVE_CLIP_LEVER == "live.avo.clip_scale"
        assert m.S.bot == "freqtrade-avo-maria" and m.S.max_open == 5
        assert abs(float(m.S.stoploss) + 0.10) < 1e-9


@pytest.mark.parametrize("name,value,attr,expect", [
    ("AVO_LOOP_SECONDS", "111", "LOOP_SECONDS", 111),
    ("AVO_DAILY_LOSS", "0.07", "DAILY_LOSS_LIMIT", 0.07),
    ("AVO_DELIST_GIVEUP_H", "9", "DELIST_GIVEUP_H", 9.0),
    ("AVO_MIN_CLIP_USD", "12", "MIN_CLIP_USD", 12.0),
    ("AVO_QUALITY_VETO_TTL_S", "60", "QUALITY_VETO_TTL_S", 60.0),
    ("AVO_GROSS_X", "3", "GROSS_X", 3.0),
    ("AVO_GROSS_X_MAX", "4", "GROSS_X_MAX", 4.0),
])
def test_every_avo_env_still_resolves(name, value, attr, expect):
    """Name by name. A prefix refactor that silently stopped reading one of
    these would change a REAL-MONEY book's sizing or its halt threshold with
    nothing to show for it."""
    with loaded(**{name: value}) as m:
        assert getattr(m, attr) == expect, f"{name} no longer reaches {attr}"


def test_a_georgia_env_does_not_leak_into_avo():
    """Two live services run this same image. If the namespaces bled, setting
    georgia's leverage would move Avo's."""
    with loaded(GEORGIA_GROSS_X="5", GEORGIA_LOOP_SECONDS="7") as m:
        assert m.GROSS_X == 1.0 and m.LOOP_SECONDS == 300


# ---- 4  the dangerous degrade -------------------------------------------

def test_an_unknown_book_REFUSES_rather_than_becoming_avo():
    """A typo must not point georgia's service at Avo's row, state key and
    live positions. This is the one failure that trades another book's money.

    [2026-08-25] "freqtrade-mum" moved OUT of this list the day she became
    live-capable (Eamon's launch call) — "freqtrade-mums" and "mum" keep the
    typo shapes covered."""
    for bad in ("freqtrade-georgi", "georgia", "freqtrade-mums", "mum", "  "):
        with pytest.raises(SystemExit):
            with loaded(bad):
                pass


# ---- 5-6  🔮 georgia ------------------------------------------------------

def test_georgia_resolves_to_her_own_identity():
    with loaded("freqtrade-georgia") as m:
        assert m.BOT_ROW == "freqtrade-georgia-lighter"
        assert m.SHADOW_ROW == "freqtrade-georgia-lshadow"
        assert m.STATE_KEY == "freqtrade-georgia-lighter:live"
        assert m._PFX == "GEORGIA"
        assert m.LIVE_CLIP_LEVER == "live.georgia.clip_scale"
        # the strategy comes from the family REGISTRY BY IDENTITY, so the live
        # and shadow arms of the same book cannot drift apart
        import lighter_family_bot as fam
        assert m.S is next(s for s in fam.STRATEGIES
                           if s.bot == "freqtrade-georgia")
        assert m.S.tf == "15m" and m.S.max_open == 5
        assert abs(float(m.S.stoploss) + 0.05) < 1e-9


def test_5x_means_something_different_on_georgia_and_the_code_knows_it():
    """Her stop is HALF Avo's, so the same multiplier is half the drawdown.
    Measured 22-Aug and this is the number the ask turns on:
        all-slots-stop at 5x : georgia 25%  |  avo 50%
        gross the 15% bar allows at N_eff 1: georgia 3.0x | avo 1.5x
    Nothing here was hand-typed for georgia — the leverage layer already reads
    `S.stoploss`, which is why a variant was the right shape."""
    with loaded("freqtrade-georgia", GEORGIA_GROSS_X="5",
                GEORGIA_GROSS_X_MAX="5") as g:
        assert g.gross_x() == 5.0
        assert abs(g.gross_x() * abs(float(g.S.stoploss)) - 0.25) < 1e-9
        assert abs(g.vol_target_gross_x(1.0) - 3.0) < 1e-6
        # the clip is the balance split across HER slots, not Avo's
        assert abs(g.clip_usd(500.0) - 500.0 * 5.0 / g.S.max_open) < 1e-9
    with loaded(AVO_GROSS_X="5", AVO_GROSS_X_MAX="5") as a:
        assert abs(a.gross_x() * abs(float(a.S.stoploss)) - 0.50) < 1e-9
        assert abs(a.vol_target_gross_x(1.0) - 1.5) < 1e-6


# ---- 6b  👩 mum — the third variant (2026-08-25, Eamon's launch call) -----

def test_mum_resolves_to_her_own_identity():
    with loaded("freqtrade-mum") as m:
        assert m.BOT_ROW == "freqtrade-mum-lighter"
        assert m.SHADOW_ROW == "freqtrade-mum-lshadow"
        assert m.STATE_KEY == "freqtrade-mum-lighter:live"
        assert m._PFX == "MUM"
        assert m.LIVE_CLIP_LEVER == "live.mum.clip_scale"
        import lighter_family_bot as fam
        assert m.S is next(s for s in fam.STRATEGIES
                           if s.bot == "freqtrade-mum")
        assert m.S.tf == "1h" and m.S.max_open == 4
        assert abs(float(m.S.stoploss) + 0.04) < 1e-9
        assert m.S.style == "oversold-1h"


def test_a_mum_env_does_not_leak_into_avo():
    """Three live services now run this image. The namespaces must not bleed."""
    with loaded(MUM_GROSS_X="5", MUM_LOOP_SECONDS="7") as m:
        assert m.GROSS_X == 1.0 and m.LOOP_SECONDS == 300


def test_5x_on_mum_is_a_20pct_all_slots_stop_and_the_bar_allows_3_75():
    """Her stop is -4%: the tightest of the three variants, so the same
    multiplier is the SMALLEST book-level risk in the family —
        all-slots-stop at 5x : mum 20% | georgia 25% | avo 50%
        gross the 15% bar allows at N_eff 1: mum 3.75x | georgia 3.0x | avo 1.5x
    Nothing hand-typed for her — the leverage layer reads `S.stoploss`."""
    with loaded("freqtrade-mum", MUM_GROSS_X="5", MUM_GROSS_X_MAX="5") as m:
        assert m.gross_x() == 5.0
        assert abs(m.gross_x() * abs(float(m.S.stoploss)) - 0.20) < 1e-9
        assert abs(m.vol_target_gross_x(1.0) - 3.75) < 1e-6
        # the clip is the balance split across HER four slots
        assert abs(m.clip_usd(500.0) - 500.0 * 5.0 / 4.0) < 1e-9


def test_georgia_cannot_boot_without_her_own_venue_env():
    """`GEORGIA_VENUE`, not `AVO_VENUE` — and the refusal must SAY so, or the
    operator is sent to fix the wrong variable (I8)."""
    src = (ROOT / "lighter_avo_live_bot.py").read_text()
    assert 'f"{_PFX}_VENUE must be EXACTLY' in src, \
        "the identity guard names a hardcoded env, not this book's"
    with loaded("freqtrade-georgia") as m:
        with pytest.raises(SystemExit) as e:
            m.main()
        assert "GEORGIA_VENUE" in str(e.value), str(e.value)


# ---- 7  the arm she consumes must exist ----------------------------------

def test_her_clip_lever_is_registered():
    """`fleet_tuning.get_lever` returns the env default for an UNREGISTERED
    name, so a live book whose arm does not exist has a dial nothing can turn
    — silent, and the reverse of registered-but-inert."""
    import fleet_tuning as ft
    for book in ("freqtrade-avo-maria", "freqtrade-georgia", "freqtrade-mum"):
        with loaded(book) as m:
            assert m.LIVE_CLIP_LEVER in ft.LEVERS, m.LIVE_CLIP_LEVER
            cage = ft.LEVERS[m.LIVE_CLIP_LEVER]
            assert cage["hi"] == 1.0, \
                "the consumer is restrict-only; hi>1 is inert authority"
            assert cage["lane"] == "lighter-live"
            # [(tb)'s lesson, applied forward] registered AND writable: the
            # lever's prefix must be in _LIVE_PREFIX_OWNERS or no author can
            # ever move it — registered-but-inert with extra steps.
            assert any(m.LIVE_CLIP_LEVER == p or m.LIVE_CLIP_LEVER.startswith(p)
                       for p in ft._LIVE_PREFIX_OWNERS), \
                f"{m.LIVE_CLIP_LEVER} is unwritable: no _LIVE_PREFIX_OWNERS entry"


# ---- 8-11  [(sy)] the liquidation arithmetic ------------------------------

def test_the_maintenance_margin_is_READ_not_hardcoded():
    """`(sr)` published `liq_gap_pct` off a literal 0.03. The venue's real
    worst across these books' own universes is 0.06 — IWM/MSTR on Avo's
    non-crypto set, ADA/DOT/AVAX/LINK once georgia's crypto set is in — so the
    row advertised a liquidation gap TWICE as far away as it was. The data was
    already on the bus ((se)) and nothing read it."""
    src = (ROOT / "lighter_avo_live_bot.py").read_text()
    assert "0.03 - 1.0 / max(1e-9, gross_x())" not in src, \
        "the hardcoded 300bps is back"
    assert "fleet_bus.market_margins()" in src, "the venue's surface is unread"


def test_an_unreadable_margin_publishes_NOTHING_rather_than_a_guess():
    """`market_margins` is fail-CLOSED because the cost of a wrong default is a
    liquidation. A fabricated distance on a levered real-money row is the one
    number that must never be invented (I8)."""
    with loaded() as m:
        assert m.worst_mmf([]) is None
        assert m.liq_gap_pct(None) is None
        assert m.stop_reachable(None) == (None, None)


@pytest.mark.parametrize("book,stop,ceiling", [
    ("freqtrade-avo-maria", 0.10, 6.25),
    ("freqtrade-georgia", 0.05, 9.09),
    # 👩 mum's -4% stop puts her ceiling at EXACTLY the operator's 10x cap:
    # 1/(0.04+0.06) = 10.0 — at 10x her stop is already dead code, so her
    # runbook's "reachable" range is strictly below the ceiling.
    ("freqtrade-mum", 0.04, 10.0),
])
def test_the_stop_has_a_gross_ceiling_of_its_own(book, stop, ceiling):
    """THE NUMBER THAT DECIDES WHAT 10x MEANS. Liquidation arrives at
    `1/G - mmf`, the stop fires at `|stoploss|` — so above
    `G = 1/(|stoploss| + mmf)` the venue liquidates FIRST and the protective
    stop is dead code. Not a risk-appetite question: a stop that cannot fire is
    a broken rail, and it was invisible until now."""
    with loaded(book) as m:
        assert abs(abs(float(m.S.stoploss)) - stop) < 1e-9
        ok, ceil = m.stop_reachable(0.06, gross=10.0)
        assert ok is False, "at 10x this stop cannot fire before liquidation"
        assert abs(ceil - ceiling) < 0.01, (ceil, ceiling)
        below, _ = m.stop_reachable(0.06, gross=ceiling - 0.5)
        assert below is True, "just under the ceiling the stop must still fire"


def test_liq_gap_matches_the_closed_form_and_keeps_its_sign():
    """`x = 1/G - mmf`, published NEGATIVE (the direction that hurts a long
    book), matching (sr)'s convention so the field's meaning did not silently
    flip when its source did."""
    with loaded() as m:
        assert m.liq_gap_pct(0.06, gross=5.0) == -0.14
        assert m.liq_gap_pct(0.06, gross=10.0) == -0.04
        assert m.liq_gap_pct(0.06, gross=0) is None


def test_the_ceiling_is_ten_and_is_a_ceiling_not_a_setting():
    """Eamon, 22-Aug: "let avo go up to 10x, and georgia also". GROSS_X_MAX is
    the bound; GROSS_X is what a service runs, and it still defaults to 1.0 —
    raising the ceiling must not lever an unconfigured book."""
    for book in ("freqtrade-avo-maria", "freqtrade-georgia", "freqtrade-mum"):
        with loaded(book) as m:
            assert m.GROSS_X_MAX == 10.0
            assert m.GROSS_X == 1.0 and m.gross_x() == 1.0


# ---- 12  [(sz)] THE BOOT SMOKE --------------------------------------------
#
# Everything above reads the module. This DRIVES it: one full cycle of the real
# `main()` as 🔮 georgia, through the real entry path, against a stub venue.
#
# It exists because `--selftest` cannot cover her. That suite is SwingDip-shaped
# — 4h dip bars, `dip_in_uptrend` tags — so under georgia it exercises the
# generic machinery and then fails on its own fixture. The honest fix was to
# make `--selftest` REFUSE a non-Avo book (a suite that runs 3 of 13 checks and
# exits 0 reports clean having inspected almost nothing), and that refusal is
# only defensible if the coverage it points at actually exists. This is it.
#
# THE FAILURE IT IS AIMED AT is the one that costs real money: georgia's
# service booting and managing 🙏 AVO'S row, state key and positions. Nothing
# above could catch that, because every check above reads a constant — this is
# the only place the identity has to survive contact with the loop.

@contextlib.contextmanager
def _driven(m, tape="breakout"):
    """Stub the venue-facing surface of `m` and hand back the capture box.

    Patches are made on the MODULE OBJECTS (`bot_pnl_store`, `venues.marks`)
    and restored on the way out, because those are shared with every other test
    in the session — a leaked `store.publish` stub would silently swallow
    another module's writes.

    `tape` picks the fixture market: "breakout" (rising, breaks the 20-bar
    high — what georgia's DayTrader and Avo's SwingDip machinery expects) or
    "oversold" (monotone fall — RSI(14) pinned low and e50 < e200, the cell
    👩 mum's OversoldRebound enters)."""
    import bot_pnl_store as store
    from venues import marks

    box = {"paper": [], "orders": [], "state": {}, "published": [],
           "printed": []}

    N = 240
    if tape == "oversold":
        c = [100.0 * (0.998 ** i) for i in range(N)]
        h = [x * 1.002 for x in c]
    else:
        c = [100.0 * (1.004 ** i) for i in range(N)]
        c[-1] = c[-2] * 1.03                # break the 20-bar high -> breakout
        h = [x * 1.005 for x in c]
        h[-1] = c[-1] * 1.001
    bars = {"t": list(range(N)), "o": c, "h": h,
            "l": [x * 0.995 for x in c], "c": c, "v": [1.0] * N}

    class _Cache:
        def __init__(self, venue):
            pass

        def get(self, coin, tf):
            return bars

    class _Venue:
        def __init__(self):
            self.opens, self.closes, self.pos = [], [], {}

        def supports(self, coin):
            return coin in ("BTC", "ETH")

        def account_value(self):
            return 200.0

        def pop_capital_moves(self):
            return []

        def positions(self):
            return dict(self.pos)

        def funding_map(self):
            return {}

        def candles(self, coin, interval, start_ms, end_ms):
            return []

        def market_open(self, coin, is_long, size):
            self.opens.append((coin, is_long, size))
            self.pos[coin] = {"size": size, "entry": c[-1]}
            return {"client_order_index": 1}

        def market_close(self, coin):
            self.closes.append(coin)
            self.pos.pop(coin, None)
            return {"client_order_index": 2}

    class _Rails:
        live = True
        max_notional = 1000.0
        max_daily_loss = 30.0

        def kill_check(self):
            return False

        def headroom_check(self, margin_state, stop_frac):
            return True, "flat"

        def daily_loss_hit(self, ds, eq):
            return False

        def confirm_daily_loss(self, ds, eq, lim, rd, delay_s=0):
            return True, eq

        def notional_ok(self, open_ntl, add):
            return (open_ntl + add) <= self.max_notional + 1e-9

    saved_store = {k: getattr(store, k, None) for k in (
        "heartbeat", "claim_writer", "snapshot_equity", "publish_paper_trade",
        "publish_venue_order", "publish", "save_state", "load_state",
        "load_state_checked", "save_daily_halt", "load_daily_halt",
        "set_status", "fetch_paper_aggregate", "service_name")}
    saved_mark = marks.fresh_mid
    saved_mod = {k: getattr(m, k) for k in (
        "CandleCache", "btc_regime_up", "btc_tide_up", "noncrypto_regimes",
        "_PRINT")}

    store.heartbeat = lambda bot: None
    store.claim_writer = lambda bot, now=None: (True, None)
    store.snapshot_equity = \
        lambda bot, eq, open_trades=None, realized=None: True
    store.publish_paper_trade = \
        lambda bot, **kw: box["paper"].append((bot, kw))
    store.publish_venue_order = \
        lambda bot, **kw: box["orders"].append((bot, kw))
    store.publish = lambda bot, **kw: box["published"].append((bot, kw))
    store.save_state = \
        lambda k, v: box["state"].__setitem__(k, v) or True
    store.load_state = lambda k: box["state"].get(k)
    store.load_state_checked = lambda k: (True, box["state"].get(k))
    store.save_daily_halt = lambda bot, day, eq=None: True
    store.load_daily_halt = lambda bot, day: None
    store.set_status = lambda bot, st: None
    store.fetch_paper_aggregate = lambda bot: None
    store.service_name = lambda: "boot-smoke"
    marks.fresh_mid = lambda venue, coin: c[-1]
    m.CandleCache = _Cache
    m.btc_regime_up = lambda cache: True
    m.btc_tide_up = lambda cache: True
    m.noncrypto_regimes = lambda: {}
    m._PRINT = lambda *a, **k: box["printed"].append(" ".join(str(x)
                                                             for x in a))
    try:
        box["venue"], box["rails"] = _Venue(), _Rails()
        yield box
    finally:
        for k, v in saved_store.items():
            if v is not None:
                setattr(store, k, v)
        marks.fresh_mid = saved_mark
        for k, v in saved_mod.items():
            setattr(m, k, v)


def test_georgia_boots_and_completes_a_cycle_as_HERSELF():
    """One real cycle. She must publish to HER row, restore HER state key, and
    never touch Avo's — the whole point of the variant host, driven rather than
    asserted about a constant."""
    with loaded("freqtrade-georgia", GEORGIA_GROSS_X="5") as m:
        with _driven(m) as box:
            m.main(_ctx={"venue": box["venue"], "rails": box["rails"]},
                   once=True)

        rows = [b for b, _ in box["published"]]
        assert rows and set(rows) == {"freqtrade-georgia-lighter"}, rows
        assert not any("avo" in r for r in rows), rows
        assert not any("avo" in k for k in box["state"]), list(box["state"])
        assert "freqtrade-georgia-lighter:live" in box["state"]

        pub = box["published"][-1][1]
        pol = pub["extra"]["policy"]
        assert pol["strategy"] == "daytrader-15m", pol
        assert pol["venue"] == "lighter_live"


def test_georgia_sizes_off_HER_geometry_not_avos():
    """`clip = equity * gross_x / max_open`. The number is hers because
    `S.max_open` is hers — this drives it rather than trusting the formula,
    which is how a variant host silently trades the wrong book's size."""
    with loaded("freqtrade-georgia", GEORGIA_GROSS_X="5") as m:
        with _driven(m) as box:
            m.main(_ctx={"venue": box["venue"], "rails": box["rails"]},
                   once=True)
            assert box["venue"].opens, "georgia's breakout must open"
            _coin, is_long, size = box["venue"].opens[0]
            assert is_long is True
            want = 200.0 * m.gross_x() / m.S.max_open
            got = size * box["venue"].pos[_coin]["entry"]
            assert abs(got - want) < 1.0, (got, want, m.gross_x(), m.S.max_open)

        ordr = box["orders"][0]
        assert ordr[0] == "freqtrade-georgia-lighter", ordr[0]
        assert ordr[1]["shadow"] is False


def test_her_cycle_publishes_the_leverage_and_scan_blocks():
    """The two censuses a levered live book is read by. `(sr)`/`(sy)` put the
    liquidation arithmetic on the row so a setting's consequences are readable
    every loop instead of re-argued; `(st)` put the scan verdicts there so
    `open: 0` is never byte-identical between "quiet" and "shut"."""
    with loaded("freqtrade-georgia", GEORGIA_GROSS_X="5") as m:
        with _driven(m) as box:
            m.main(_ctx={"venue": box["venue"], "rails": box["rails"]},
                   once=True)
        extra = box["published"][-1][1]["extra"]
        lev = extra["leverage"]
        assert lev["set"] == 5.0
        # UNIT: these are FRACTIONS despite the `_pct` suffix, which is (sr)'s
        # convention and is pinned here because I got it wrong writing this
        # test. 0.25 = a 25% book-level loss if all five slots stop together.
        assert lev["all_slots_stop_pct"] == 0.25, lev
        assert "scan" in extra and extra["scan"]

    # The same setting on 🙏 Avo costs TWICE as much, because her stop is twice
    # as wide. Both in one test so "5x" can never read as one number again.
    with loaded(AVO_GROSS_X="5") as a:
        with _driven(a) as box:
            a.main(_ctx={"venue": box["venue"], "rails": box["rails"]},
                   once=True)
        assert box["published"][-1][1]["extra"]["leverage"][
            "all_slots_stop_pct"] == 0.50


def test_mum_boots_and_completes_a_cycle_as_HERSELF():
    """[(sz)'s lesson, applied to the third variant before it costs money.]
    One real cycle of `main()` as 👩 mum against an oversold tape: she must
    publish to HER row, restore HER state key, open on HER cell
    (`oversold-rebound`) and size off HER geometry (4 slots), never Avo's or
    georgia's. Every check above reads a constant — this is where her
    identity survives contact with the loop."""
    with loaded("freqtrade-mum", MUM_GROSS_X="2") as m:
        with _driven(m, tape="oversold") as box:
            m.main(_ctx={"venue": box["venue"], "rails": box["rails"]},
                   once=True)

        rows = [b for b, _ in box["published"]]
        assert rows and set(rows) == {"freqtrade-mum-lighter"}, rows
        assert not any("avo" in r or "georgia" in r for r in rows), rows
        assert not any("avo" in k or "georgia" in k for k in box["state"]), \
            list(box["state"])
        assert "freqtrade-mum-lighter:live" in box["state"]

        assert box["venue"].opens, "mum's oversold entry must open"
        _coin, is_long, size = box["venue"].opens[0]
        assert is_long is True
        want = 200.0 * m.gross_x() / m.S.max_open       # HER four slots
        got = size * box["venue"].pos[_coin]["entry"]
        assert abs(got - want) < 1.0, (got, want, m.gross_x(), m.S.max_open)

        pub = box["published"][-1][1]
        pol = pub["extra"]["policy"]
        assert pol["strategy"] == "oversold-1h", pol
        assert pol["venue"] == "lighter_live"
        ordr = box["orders"][0]
        assert ordr[0] == "freqtrade-mum-lighter", ordr[0]
        assert ordr[1]["shadow"] is False
        # [(te)] the I22 spend census, complete on every publish — the guard's
        # first real test was this host's own variants, and it fired.
        spend = pub["extra"]["spend"]
        for f in ("markets_scanned", "n_eff", "sides", "gross_x",
                  "days_to_gate_obs"):
            assert spend.get(f) is not None, (f, spend)
        assert spend["sides"] == "long"
        assert 0.0 <= spend["days_to_gate_obs"] <= 30.0, spend


def test_manual_pnl_attestation_reaches_the_row_and_only_the_row():
    """[2026-08-25 (td)] Eamon's manual trades flowed into 🙏 Avo's published
    P&L (venue equity cannot tell his fills from the bot's), so the board cut
    her clip 0.75x for losses that were never hers. `<PFX>_MANUAL_PNL_USD`
    attests the manual total and holds it OUT of pnl_abs — per-book (a mum
    attestation must not move Avo), a LEVEL (idempotent), garbage -> 0.0, and
    ALWAYS published so 0.0 is visible rather than absent."""
    # per-book namespacing + garbage degrade
    with loaded(MUM_MANUAL_PNL_USD="-50") as m:
        assert m.MANUAL_PNL_USD == 0.0, "mum's attestation leaked into Avo"
    with loaded(AVO_MANUAL_PNL_USD="abc") as m:
        assert m.MANUAL_PNL_USD == 0.0
    with loaded(AVO_MANUAL_PNL_USD="nan") as m:
        assert m.MANUAL_PNL_USD == 0.0
    # the fold, driven through a real cycle: published pnl_abs excludes the
    # attested manual total, while equity stays venue truth
    with loaded(AVO_MANUAL_PNL_USD="-66.4") as m:
        assert m.MANUAL_PNL_USD == -66.4
        with _driven(m) as box:
            m.main(_ctx={"venue": box["venue"], "rails": box["rails"]},
                   once=True)
        pub = box["published"][-1][1]
        ex = pub["extra"]
        assert ex["manual_pnl_usd"] == -66.4
        # equity 200, no baseline in fresh state -> baseline adopts equity,
        # so pnl reads -cap_adj - manual = +66.4 relative fold; the exact
        # value depends on the adopt path — assert the FOLD, not the level:
        # a zero-attestation run of the same fixture must differ by 66.4.
        pnl_with = pub["pnl_abs"]
    with loaded() as m0:
        with _driven(m0) as box0:
            m0.main(_ctx={"venue": box0["venue"], "rails": box0["rails"]},
                    once=True)
        pub0 = box0["published"][-1][1]
        assert pub0["extra"]["manual_pnl_usd"] == 0.0, \
            "zero must be published, not omitted"
        if pnl_with is not None and pub0["pnl_abs"] is not None:
            assert abs((pnl_with - pub0["pnl_abs"]) - 66.4) < 0.02, \
                (pnl_with, pub0["pnl_abs"])


def test_custom_exit_fires_on_the_LIVE_arm():
    """[2026-08-25] THE HOST NEVER CALLED S.custom_exit. The family loop has
    called it duck-typed since (ro) (stop -> roi -> custom_exit -> signal);
    the live runner checked stop, roi and signal only — so 🔮 georgia's live
    arm ran real money without her bounce_take/bounce_timeout/max_hold_timeout,
    and 👩 mum's 24h carry cap would have been dead code on her live arm: a
    position sitting between 0 and the stop had NO exit at all, which is v1's
    disease (a month-long hold) reborn on the arm that holds real money.

    Driven, not asserted: a restored position aged past the cap at −1% (no
    stop, no roi rung, no exit signal) must close by the time cap alone."""
    import time as _t
    last = 100.0 * (0.998 ** 239)          # the oversold tape's final close
    with loaded("freqtrade-mum") as m:
        with _driven(m, tape="oversold") as box:
            box["state"]["freqtrade-mum-lighter:live"] = {
                "meta": {"BTC": {"entry": last * 1.0101,
                                 "opened_ts": _t.time() - 25 * 3600.0,
                                 "tag": "oversold-rebound"}}}
            box["venue"].pos["BTC"] = {"size": 0.5, "entry": last * 1.0101}
            m.main(_ctx={"venue": box["venue"], "rails": box["rails"]},
                   once=True)
            assert "BTC" in box["venue"].closes, box["venue"].closes
        reasons = [str(kw.get("reason")) for _, kw in box["paper"]]
        assert any("max_hold" in r for r in reasons), reasons

    last = 100.0 * (1.004 ** 238) * 1.03   # the breakout tape's final close
    with loaded("freqtrade-georgia") as g:
        with _driven(g) as box:
            box["state"]["freqtrade-georgia-lighter:live"] = {
                "meta": {"ETH": {"entry": last * 1.0101,
                                 "opened_ts": _t.time() - 25 * 3600.0,
                                 "tag": "range_on"}}}
            box["venue"].pos["ETH"] = {"size": 0.1, "entry": last * 1.0101}
            g.main(_ctx={"venue": box["venue"], "rails": box["rails"]},
                   once=True)
            assert "ETH" in box["venue"].closes, box["venue"].closes
        reasons = [str(kw.get("reason")) for _, kw in box["paper"]]
        assert any("max_hold_timeout" in r for r in reasons), reasons


def test_the_boot_gate_names_HER_cap_env_not_avos():
    """I8 on the one instruction a real-money service prints as it refuses to
    start. This message named `FREQTRADE_AVO_MARIA_MAX_NOTIONAL` verbatim, so
    georgia's operator would have been sent to set another book's cap."""
    with loaded("freqtrade-georgia") as m:
        with _driven(m) as box:
            box["rails"].max_notional = None
            with pytest.raises(SystemExit) as e:
                m.main(_ctx={"venue": box["venue"], "rails": box["rails"]},
                       once=True)
        assert "FREQTRADE_GEORGIA_MAX_NOTIONAL" in str(e.value), str(e.value)
        assert "AVO" not in str(e.value), str(e.value)
    # ...and 👩 mum's refusal names HER cap, for the same I8 reason.
    with loaded("freqtrade-mum") as m:
        with _driven(m, tape="oversold") as box:
            box["rails"].max_notional = None
            with pytest.raises(SystemExit) as e:
                m.main(_ctx={"venue": box["venue"], "rails": box["rails"]},
                       once=True)
        assert "FREQTRADE_MUM_MAX_NOTIONAL" in str(e.value), str(e.value)
        assert "AVO" not in str(e.value) and "GEORGIA" not in str(e.value), \
            str(e.value)


def test_selftest_REFUSES_a_non_avo_book_rather_than_half_running():
    """The refusal the test above exists to justify. `--selftest` is
    SwingDip-shaped; under georgia it would run a handful of generic checks and
    then die on its own fixture. A suite that inspects almost nothing and exits
    0 is the "a check that inspects nothing reports clean" trap — so it exits
    NON-ZERO and names where her coverage actually lives.

    Driven as a subprocess because the thing under test is the process's exit
    code, and an in-process `SystemExit` catch would prove something weaker."""
    import subprocess
    env = dict(os.environ, FAMILY_LIVE_BOOK="freqtrade-georgia")
    env.pop("DATABASE_URL", None)
    p = subprocess.run(
        [sys.executable, "lighter_avo_live_bot.py", "--selftest"],
        cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=120)
    assert p.returncode != 0, p.stdout[-2000:]
    out = p.stdout + p.stderr
    assert "test_variant_host" in out, out[-2000:]

    # ...and the Avo path it protects is UNCHANGED: the same command with no
    # book set must still run the real suite green. Without this half, the
    # refusal above is satisfiable by breaking --selftest for everybody.
    env2 = dict(os.environ)
    env2.pop("FAMILY_LIVE_BOOK", None)
    env2.pop("DATABASE_URL", None)
    q = subprocess.run(
        [sys.executable, "lighter_avo_live_bot.py", "--selftest"],
        cwd=str(ROOT), env=env2, capture_output=True, text=True, timeout=300)
    assert q.returncode == 0, (q.stdout[-3000:], q.stderr[-2000:])


# ---- [(th)] the improvement round's pins ----------------------------------
# Ten weakened candidates survived the adversarial pass; these drive the ones
# that ship in the live host. Every pin runs the REAL main() against the
# publisher its consumers read ((hj): never a hand-written fixture).

def test_entry_rank_is_born_at_the_open_and_reaches_the_close():
    """Three sites or it is vacuous: rank computed at the OPEN (clock-hour
    bucket in the DURABLE state, so a mid-hour restart cannot under-rank),
    carried on meta, copied to the close row. The one-site draft stamped only
    the close and would have published None forever — the exact vacuous
    instrument the verify pass caught. DECLARED divergence, pinned by name:
    the live host enforces no hourly throttle, so live rank is the UNCENSORED
    within-hour ordinal."""
    with loaded("freqtrade-georgia", GEORGIA_GROSS_X="5") as m:
        with _driven(m) as box:
            # a STALE bucket from a previous hour, restored at boot: without
            # the reset, ranks continue from 7 and the first open stamps 8 —
            # the mutation that survived this test's first draft.
            box["state"]["freqtrade-georgia-lighter:live"] = {
                "rank_bucket": 0, "rank_n": 7}
            m.main(_ctx={"venue": box["venue"], "rails": box["rails"]},
                   once=True)
            st = box["state"]["freqtrade-georgia-lighter:live"]
            metas = st["meta"]
            assert box["venue"].opens, "the breakout tape must open"
            ranks = sorted(v.get("entry_rank") for v in metas.values())
            assert ranks == list(range(1, len(metas) + 1)), metas
            assert st.get("rank_n") == len(metas), st.get("rank_n")
            # kill-flatten the second cycle: every close row must carry the
            # rank its OPEN recorded.
            box["rails"].kill_check = lambda: True
            m.main(_ctx={"venue": box["venue"], "rails": box["rails"]},
                   once=True)
        assert box["paper"], "the kill flatten must book real closes"
        got = {kw["pair"]: kw["extra"].get("entry_rank")
               for _b, kw in box["paper"]}
        assert sorted(got.values()) == list(range(1, len(got) + 1)), got
        # real closes with a real entry price are NEVER phantom-tagged
        assert all("non_economic" not in kw["extra"]
                   for _b, kw in box["paper"]), box["paper"]


def test_mum_control_pair_settles_through_the_one_owner():
    """The (rp) atomic pair on the LIVE host: the open draws the placebo (one
    venue mid), the close settles both legs or neither, and the row publishes
    `control` ALWAYS — n=0 included — from her own real-money ledger. Also
    pins the identity rule ((hj)): the live host's control machinery IS the
    family module's objects, never a re-typed copy, because this is the
    number her go-live verdict and every leverage notch will be judged on.
    And mum has no throttle carrier, so her rank stamps None — never a fake
    1 ((sv))."""
    import lighter_family_bot as fam
    with loaded("freqtrade-mum", MUM_GROSS_X="9.5") as m:
        assert m.control_draw is fam.control_draw
        assert m.control_settle is fam.control_settle
        assert m.control_block is fam.control_block
        with _driven(m, tape="oversold") as box:
            m.main(_ctx={"venue": box["venue"], "rails": box["rails"]},
                   once=True)
            st = box["state"]["freqtrade-mum-lighter:live"]
            assert st["meta"], "the oversold tape must open"
            n_opened = len(st["meta"])
            for v in st["meta"].values():
                assert v.get("entry_rank") is None, v
                assert v.get("null_pair") and v.get("null_entry"), v
            # BEFORE any close: the block is already on the row at n=0 —
            # "no closes yet" must never be byte-identical to "not running"
            first = box["published"][0][1]["extra"]["control"]
            assert first["n"] == 0 and first["null_n"] == 0, first
            box["rails"].kill_check = lambda: True
            m.main(_ctx={"venue": box["venue"], "rails": box["rails"]},
                   once=True)
        ctrl = box["published"][-1][1]["extra"]["control"]
        assert ctrl["n"] == ctrl["null_n"] == n_opened, ctrl
        assert ctrl["mean_pct"] is not None
        assert ctrl["null_pct"] is not None
        assert ctrl["edge_pct"] is not None


def test_a_non_control_book_payload_does_not_move():
    """{} for avo/georgia — the control block must not appear on books that
    run no control arm, or every grader learns a phantom key."""
    with loaded("freqtrade-georgia", GEORGIA_GROSS_X="5") as m:
        with _driven(m) as box:
            m.main(_ctx={"venue": box["venue"], "rails": box["rails"]},
                   once=True)
        assert "control" not in box["published"][-1][1]["extra"]


def test_the_halt_geometry_and_ruin_verdict_are_on_the_row():
    """(th): both daily rails are gross-BLIND, so the row now publishes the
    COUPLED number — at mum's 9.5x the day ends on a ~1.05% adverse basket
    move — beside the ruin gate's verdict, every loop. A number on the
    payload outlives an argument in a message."""
    with loaded("freqtrade-mum", MUM_GROSS_X="9.5") as m:
        with _driven(m, tape="oversold") as box:
            m.main(_ctx={"venue": box["venue"], "rails": box["rails"]},
                   once=True)
        extra = box["published"][-1][1]["extra"]
        lev = extra["leverage"]
        halt = lev["halt"]
        assert halt["daily_loss_frac"] == 0.10
        assert halt["abs_usd"] == 30.0
        assert halt["basket_move_at_full_gross_pct"] == round(0.10 / 9.5, 4)
        # stub day-start 200: abs $30 > pct $20, so the pct rail binds
        assert halt["binding"] == "pct", halt
        hd = lev["headroom"]
        assert set(hd) == {"ok", "reason", "gap_stop_widths"}, hd
        ov = extra["stop_overshoot"]
        assert ov == {"n": 0, "unmeasured_n": 0, "p90_bps": None,
                      "worst_bps": None}, ov


def test_an_unmeasured_stop_fill_counts_in_its_own_bucket_never_zero():
    """I14: an unmeasured fill imputed as zero overshoot would bias — in the
    optimistic direction — the exact number a future gross ceiling consumes.
    The stub venue measures nothing, so a driven stop close must land in
    `unmeasured_n`, leave n=0/p90=None, and stamp no per-close bps."""
    with loaded("freqtrade-georgia", GEORGIA_GROSS_X="5") as m:
        with _driven(m) as box:
            m.main(_ctx={"venue": box["venue"], "rails": box["rails"]},
                   once=True)
            st = box["state"]["freqtrade-georgia-lighter:live"]
            assert st["meta"], "the breakout tape must open"
            coin = next(iter(st["meta"]))
            # raise the recorded entry so the flat stop fires on cycle 2
            st["meta"][coin]["entry"] = st["meta"][coin]["entry"] * 1.10
            m.main(_ctx={"venue": box["venue"], "rails": box["rails"]},
                   once=True)
        stops = [kw for _b, kw in box["paper"] if "stop" in kw["reason"]]
        assert stops, [kw["reason"] for _b, kw in box["paper"]]
        assert all("stop_overshoot_bps" not in kw["extra"]
                   for kw in stops), stops
        ov = box["published"][-1][1]["extra"]["stop_overshoot"]
        assert ov["unmeasured_n"] >= 1 and ov["n"] == 0, ov
        assert ov["p90_bps"] is None, ov


def test_a_zero_dollar_no_entry_close_is_tagged_non_economic():
    """The phantom signature at the write site: $0.00 AND no entry price —
    never the reason string, which a REAL forced-flatten loss shares."""
    with loaded("freqtrade-georgia", GEORGIA_GROSS_X="5") as m:
        with _driven(m) as box:
            m.main(_ctx={"venue": box["venue"], "rails": box["rails"]},
                   once=True)
            st = box["state"]["freqtrade-georgia-lighter:live"]
            assert st["meta"]
            coin = next(iter(st["meta"]))
            st["meta"][coin]["entry"] = 0.0        # a meta with no fill data
            box["rails"].kill_check = lambda: True
            m.main(_ctx={"venue": box["venue"], "rails": box["rails"]},
                   once=True)
        ph = [kw for _b, kw in box["paper"]
              if kw["extra"].get("non_economic")]
        assert len(ph) == 1 and ph[0]["pair"] == coin, box["paper"]
        assert ph[0]["pnl_abs"] == 0.0 and ph[0]["entry_price"] is None
        # ...and the coin with real fill data in the same flatten is NOT
        others = [kw for _b, kw in box["paper"]
                  if not kw["extra"].get("non_economic")]
        assert all(kw["entry_price"] for kw in others), others


def test_pnl_pct_is_denominated_on_contributed_capital():
    """avo's row read −96.9% where the capital-honest figure is −26%: the
    $167.76 deposit grew the capital and the birth-equity basis never saw
    it. Display-side only — the graded per-trade sample is untouched."""
    with loaded(AVO_GROSS_X="5") as m:
        with _driven(m) as box:
            box["state"]["freqtrade-avo-maria-lighter:live"] = {
                "initial_equity": 50.0,
                "capital_adjust": {"total": 100.0}}
            m.main(_ctx={"venue": box["venue"], "rails": box["rails"]},
                   once=True)
        pub = box["published"][-1][1]
        assert pub["pnl_abs"] == 50.0, pub          # 200 − 50 − 100
        assert pub["pnl_pct"] == round(50.0 / 150.0, 6), pub
