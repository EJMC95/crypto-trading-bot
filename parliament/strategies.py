#!/usr/bin/env python3
"""
parliament/strategies.py — Layer 4: the six PM trading bots.

Six SHADOW $1,000 books (fleet rules: no top-ups, paper until the go-live
gate), each consuming Keating's signals + ML gate and publishing to the
dashboard exactly like every other fleet citizen. Fills are modelled at
Lighter's own last/mark price with an explicit slippage charge (live ws
half-spread when fresh, a conservative default otherwise) — zero fee, like
Lighter's standard tier; slippage IS the cost, same doctrine as
venues/shadow.py.

WHO TRADES WHAT
  pm-albanese 🏗️ trend    — trend_alignment, confirmed by momentum_burst
  pm-morrison 📣 breakout — Donchian break, confirmed by volume_spike
  pm-turnbull 💼 meanrev  — RSI stretch fade, vetoed in expanding vol
  pm-abbott   🥊 scalp    — strong momentum bursts, tight TP/SL, short hold
  pm-rudd     🌏 funding  — holds the side funding PAYS, trend-sanity-checked
  pm-gillard  🤝 disloc   — fades mark-vs-index premium, exits on reconverge

EVERY entry passes the same gate stack, in order:
  1. fresh market data (dark data = no trade, never a stale-price fill)
  2. Howard's venue-stress pause (|prem| median >= 15bps — the taker's bar)
  3. the fleet L2 long-budget veto (fleet_bus.long_entries_blocked)
  4. per-book risk: max open, per-coin cooldown, notional cap, daily-loss halt
  5. the ML gate — REDUCE-ONLY: skip or shrink stake, never boost, and the
     brain's per-(bot, tag) stake mult (fleet_bus.stake_multiplier) on top
Closes are tagged `<side>-<lens>_<exit>` (the Ticket Taker's convention) so
bot_learn grades every lens on real forward returns.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import datetime, timezone

from . import PM_BOTS, SHADOW_SUFFIX, START_EQUITY
from .bus import drain
from .ml import featurize

try:
    from paper_broker import PaperBroker
except Exception:  # noqa: BLE001 — repo root not on path (never in prod)
    PaperBroker = None

try:
    import bot_pnl_store as store
except Exception:  # noqa: BLE001
    store = None

try:
    import fleet_bus
except Exception:  # noqa: BLE001
    fleet_bus = None

log = logging.getLogger("parliament.bots")

ORDER_USD = float(os.environ.get("PARL_ORDER_USD", "25"))
MAX_OPEN = int(os.environ.get("PARL_MAX_OPEN", "3"))
MAX_NOTIONAL = float(os.environ.get("PARL_MAX_NOTIONAL", "150"))
DAILY_HALT_USD = float(os.environ.get("PARL_DAILY_HALT_USD", "50"))
COIN_COOLDOWN_SEC = float(os.environ.get("PARL_COIN_COOLDOWN_SEC", "3600"))
SIGNAL_TTL_SEC = float(os.environ.get("PARL_SIGNAL_TTL_SEC", "900"))
DEFAULT_SLIP_BPS = float(os.environ.get("PARL_DEFAULT_SLIP_BPS", "5"))

# Tunable per-bot parameters and their HARD bounds — the registry the tuners
# clamp to (fleet_tuning doctrine: a lever can only move inside its bounds,
# and expiry reverts to baseline).
PARAM_BOUNDS = {
    "tp_pct":      (0.008, 0.08),
    # [2026-08-13 (lq)] sl_pct hi 0.05 -> 0.08 — REACH, not a set value
    # (I18: the binding constraint must be a reachable lever). The (gx)
    # exit sweep on gillard — the ONE book whose replay passes the
    # calibration gate — measured the direction robust and MONOTONE:
    # sl 1.0% -> −0.158%/trade, 1.5% -> −0.098, 2.0% -> −0.034,
    # 3.0% -> +0.050, with drawdown FALLING 40.7% -> 26.0% (the tight stop
    # was REALISING the losses), and every top candidate pinned sl at the
    # grid's edge — "the honest output is 'widen the grid', not 'ship 8%'".
    # (gx)'s own review note named this cage as the blocker: the sweep's
    # winner sat OUTSIDE what the system can express. The hi moves to the
    # sweep's grid edge; DEFAULTS ARE UNCHANGED — the Parliament's
    # replay-gated tuners walk there only if each ×1.25 step keeps passing
    # their own gate, which the measured table says the steps do.
    "sl_pct":      (0.005, 0.08),
    "max_hold_hr": (2.0, 96.0),
    "entry_bar":   (0.20, 0.90),
    # [2026-07-28 honesty note] ml_gate is REGISTERED (the cage clamps any
    # future author) but currently has NO autonomous author: the exit-replay
    # sweep walks tp/sl/hold only (it structurally cannot judge an entry
    # filter), and entry_bar's sole author is the starving widen. Until an
    # entry-side harness exists (replay stored entry features through the
    # CURRENT model at candidate gate values), ml_gate moves by env only —
    # the registry advertises reach, this line keeps it from advertising a
    # self-tuning capability that does not exist.
    "ml_gate":     (0.35, 0.60),
}

STRATEGY_DEFAULTS = {
    "trend":    {"tp_pct": 0.05,  "sl_pct": 0.025, "max_hold_hr": 48.0,
                 "entry_bar": 0.30, "ml_gate": 0.45},
    "breakout": {"tp_pct": 0.04,  "sl_pct": 0.02,  "max_hold_hr": 24.0,
                 "entry_bar": 0.35, "ml_gate": 0.45},
    "meanrev":  {"tp_pct": 0.02,  "sl_pct": 0.015, "max_hold_hr": 12.0,
                 "entry_bar": 0.30, "ml_gate": 0.45},
    "scalp":    {"tp_pct": 0.012, "sl_pct": 0.008, "max_hold_hr": 4.0,
                 "entry_bar": 0.60, "ml_gate": 0.48},
    "funding":  {"tp_pct": 0.03,  "sl_pct": 0.02,  "max_hold_hr": 72.0,
                 "entry_bar": 0.25, "ml_gate": 0.45},
    "disloc":   {"tp_pct": 0.01,  "sl_pct": 0.01,  "max_hold_hr": 6.0,
                 "entry_bar": 0.30, "ml_gate": 0.45},
}

# Which bus topics feed which strategy (primary, confirmer-or-None).
STRATEGY_TOPICS = {
    "trend":    ("signals.trend_alignment", "signals.momentum_burst"),
    "breakout": ("signals.breakout", "signals.volume_spike"),
    "meanrev":  ("signals.mean_reversion", "signals.volatility_regime"),
    "scalp":    ("signals.momentum_burst", None),
    "funding":  ("signals.funding_extreme", None),
    "disloc":   ("signals.dislocation", None),
}

LENS = {"trend": "trend", "breakout": "breakout", "meanrev": "meanrev",
        "scalp": "burst", "funding": "funding", "disloc": "disloc"}


def clamp_params(p: dict) -> dict:
    out = dict(p)
    for k, (lo, hi) in PARAM_BOUNDS.items():
        if k in out:
            out[k] = max(lo, min(hi, float(out[k])))
    return out


def base_params(strategy: str, bot_base: str) -> dict:
    """Defaults <- env overrides (PM_ABBOTT_TP_PCT=0.02 style), clamped."""
    p = dict(STRATEGY_DEFAULTS[strategy])
    prefix = bot_base.replace("pm-", "PM_").replace("-", "_").upper() + "_"
    for k in p:
        env = os.environ.get(prefix + k.upper())
        if env:
            try:
                p[k] = float(env)
            except ValueError:
                pass
    return clamp_params(p)


def _utc_day() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class PMBot:
    def __init__(self, base_id: str, strategy: str, data, bus, db, ml,
                 howard=None):
        self.base = base_id
        self.bot_id = base_id + SHADOW_SUFFIX
        self.strategy = strategy
        self.lens = LENS[strategy]
        self.data = data
        self.bus = bus
        self.db = db
        self.ml = ml
        self.howard = howard
        self.broker = PaperBroker(START_EQUITY, fee_bps=0.0) if PaperBroker else None
        self.params = base_params(strategy, base_id)
        primary, confirm = STRATEGY_TOPICS[strategy]
        topics = [primary] + ([confirm] if confirm else [])
        self.queue = bus.subscribe(*topics) if bus is not None else None
        self.primary_topic = primary
        self.confirm_topic = confirm
        self.signals: dict[tuple, dict] = {}       # (topic, sym) -> signal
        self.open_meta: dict[str, dict] = {}       # coin -> entry context
        self.last_entry: dict[str, float] = {}     # coin -> ts (cooldown)
        self.wins = 0
        self.losses = 0
        self.day = _utc_day()
        self.day_anchor = 0.0                      # realized-fees at day start
        self.halted_today = False
        self._restored = False
        self.last_skip = ""                        # observability: why no trade
        self.fund_realized = 0.0                   # funding accrued, book-life
        self._fund_ts = None                       # last accrual timestamp

    # -- durable state --------------------------------------------------------
    def restore(self) -> None:
        """[2026-07-21 AUDIT FIX] read-FAILED is not fresh-book: the old
        load_state read collapsed the two (the exact trap its own docstring
        warns about — the 17-Jul perp-sniper incident), so a transient
        Postgres blip on first cycle started a fresh $1000 book and the
        unconditional save() then OVERWROTE the durable equity curve.
        load_state_checked distinguishes them; on a failed read we stay
        un-restored (save() refuses until a clean read) and retry next
        cycle."""
        if store is None or self.broker is None:
            self._restored = True
            return
        try:
            if hasattr(store, "load_state_checked"):
                ok, st = store.load_state_checked(self.bot_id)
            else:
                ok, st = True, store.load_state(self.bot_id)
        except Exception:  # noqa: BLE001
            ok, st = False, None
        if not ok:
            log.warning("%s state read FAILED — not seeding a fresh book "
                        "over a blip; retrying next cycle", self.bot_id)
            return
        self._restored = True
        if not st:
            return
        try:
            if st.get("broker"):
                self.broker.restore_state(st["broker"])
            self.wins = int(st.get("wins", 0))
            self.losses = int(st.get("losses", 0))
            self.open_meta = {str(k): v for k, v in
                              (st.get("open_meta") or {}).items()}
            self.day = st.get("day") or self.day
            self.day_anchor = float(st.get("day_anchor", 0.0))
            self.fund_realized = float(st.get("fund_realized", 0.0))
            log.info("%s restored: eq=%.2f open=%d closed=%d",
                     self.bot_id, self.broker.equity(), len(self.broker.pos),
                     self.wins + self.losses)
        except Exception as e:  # noqa: BLE001
            log.warning("%s state restore failed (%s) — fresh book", self.bot_id, e)

    def save(self) -> None:
        if store is None or self.broker is None:
            return
        if not self._restored:
            return      # never overwrite durable state we could not read
        try:
            store.save_state(self.bot_id, {
                "broker": self.broker.to_state(),
                "wins": self.wins, "losses": self.losses,
                "open_meta": self.open_meta,
                "day": self.day, "day_anchor": self.day_anchor,
                "fund_realized": round(self.fund_realized, 6),
            })
        except Exception:  # noqa: BLE001
            pass

    # -- signal intake --------------------------------------------------------
    async def _ingest(self) -> None:
        if self.queue is None:
            return
        for topic, sig in await drain(self.queue):
            self.signals[(topic, sig["sym"])] = sig
        cutoff = time.time() - SIGNAL_TTL_SEC
        self.signals = {k: s for k, s in self.signals.items()
                        if s["ts"] >= cutoff}

    def _fresh_signal(self, topic: str, sym: str) -> dict | None:
        s = self.signals.get((topic, sym))
        if s and time.time() - s["ts"] <= SIGNAL_TTL_SEC:
            return s
        return None

    # -- pricing --------------------------------------------------------------
    def _slip_bps(self, sym: str) -> float:
        ws = (self.data.ws_books or {}).get(sym)
        if ws and time.time() - ws["ts"] < 120:
            return max(1.0, ws["spread_bps"] / 2.0)
        return DEFAULT_SLIP_BPS

    def _fill_px(self, sym: str, is_buy: bool) -> float | None:
        st = self.data.stats(sym)
        if not st:
            return None
        px = st["last"] or st["mark"]
        if px <= 0:
            return None
        slip = self._slip_bps(sym) / 1e4
        return px * (1.0 + slip) if is_buy else px * (1.0 - slip)

    # -- risk gates -----------------------------------------------------------
    def _day_roll(self) -> None:
        today = _utc_day()
        if today != self.day:
            self.day = today
            self.day_anchor = self.broker.realized - self.broker.fees
            self.halted_today = False

    def _day_pnl(self) -> float:
        return (self.broker.realized - self.broker.fees) - self.day_anchor

    def _open_notional(self) -> float:
        """Each held position at ITS OWN entry (the venues/safety.py
        open_notional rule — never count * current clip)."""
        return sum(abs(s) * e for s, e in self.broker.pos.values())

    def _entry_blocked(self, sym: str, direction: int) -> str | None:
        if not self.data.fresh():
            return "stale-data"
        if self.howard is not None and self.howard.stress_pause:
            return "venue-stress"
        if direction > 0 and fleet_bus is not None:
            try:
                if fleet_bus.long_entries_blocked():
                    return "fleet-long-budget"
            except Exception:  # noqa: BLE001
                pass
        if len(self.broker.pos) >= MAX_OPEN:
            return "max-open"
        if sym in self.broker.pos:
            return "already-in"
        if time.time() - self.last_entry.get(sym, 0.0) < COIN_COOLDOWN_SEC:
            return "cooldown"
        self._day_roll()
        if self._day_pnl() <= -DAILY_HALT_USD:
            if not self.halted_today:
                self.halted_today = True
                log.warning("%s daily-loss halt (day pnl %.2f)",
                            self.bot_id, self._day_pnl())
            return "daily-halt"
        if self._open_notional() + ORDER_USD > MAX_NOTIONAL:
            return "notional-cap"
        return None

    # -- entry ----------------------------------------------------------------
    def _candidates(self) -> list[tuple[str, int, dict]]:
        """Strategy-specific (sym, direction, primary_signal) candidates."""
        out = []
        bar = self.params["entry_bar"]
        for (topic, sym), sig in list(self.signals.items()):
            if topic != self.primary_topic or sig["strength"] < bar:
                continue
            direction = sig["direction"]
            if direction == 0:
                continue
            if self.strategy == "trend":
                burst = self._fresh_signal("signals.momentum_burst", sym)
                if burst is None or burst["direction"] != direction:
                    continue
            elif self.strategy == "breakout":
                vol = self._fresh_signal("signals.volume_spike", sym)
                if sig["strength"] < 0.5 and (
                        vol is None or vol["direction"] != direction):
                    continue
            elif self.strategy == "meanrev":
                reg = self._fresh_signal("signals.volatility_regime", sym)
                if reg is not None and reg["meta"].get("regime") == "expanding":
                    continue
            elif self.strategy == "funding":
                st = self.data.stats(sym) or {}
                # sanity: don't hold against a >2%/day trend just for carry.
                # [2026-07-21 AUDIT FIX] `chg` is the venue's daily change in
                # PERCENT units (the scout's dip lens reads -8.0..-1.0 on the
                # same field) — the original 0.10 bar therefore vetoed any
                # book moving more than 0.1%/day, i.e. essentially all of
                # them, and starved the Funding Diplomat at birth.
                if abs(st.get("chg") or 0.0) > 2.0:
                    continue
            out.append((sym, direction, sig))
        return out

    def _try_enter(self, sym: str, direction: int, sig: dict) -> bool:
        why = self._entry_blocked(sym, direction)
        if why:
            self.last_skip = f"{sym}:{why}"
            return False
        # [2026-07-28 BRAIN ACTS, Parliament lane] the brain's ACTIONABLE
        # regime_gate finding finally has a consumer here — pm-gillard's
        # long-disloc gate sat ACTIONABLE 77 consecutive runs (~6.4d, the
        # fleet's loudest finding) steering nothing, because only the family
        # bot ever wired entry_regime_gated. Identical semantics: restrict-
        # only (skips a NEW entry when the brain measured this (bot, tag)'s
        # losses clustering in risk-off AND the oracle reads risk-off NOW),
        # fail-safe OPEN on stale brain/oracle, centrally kill-switched via
        # BRAIN_ACTIONS_MODE=advisory. Shadow-only by construction.
        _gate_tag = f"{'long' if direction > 0 else 'short'}-{self.lens}"
        if fleet_bus is not None:
            try:
                if fleet_bus.entry_regime_gated(self.bot_id, _gate_tag):
                    self.last_skip = f"{sym}:brain-regime-gate"
                    return False
            except Exception:  # noqa: BLE001
                pass
        feats = featurize(sym, direction, self.data, sig)
        p_win, ready = self.ml.predict(feats) if self.ml else (0.5, False)
        stake_mult = 1.0
        if ready:
            if p_win < self.params["ml_gate"]:
                self.last_skip = f"{sym}:ml-gate({p_win:.2f})"
                return False
            if p_win < 0.55:
                stake_mult = 0.6            # tepid conviction -> smaller clip
        tag = f"{'long' if direction > 0 else 'short'}-{self.lens}"
        if fleet_bus is not None:
            try:  # the fleet brain's TWO-WAY per-(bot, tag) multiplier
                stake_mult *= fleet_bus.stake_multiplier(self.bot_id, tag)
            except Exception:  # noqa: BLE001
                pass
        # [2026-07-21 AUDIT FIX, same day as BRAIN WIDENS] the ceiling was
        # min(1.0), which silently truncated the brain's new 1.25x/1.5x
        # expand mults in all six PM books on the very day the operator
        # mandated the widening. Cap at the bus's own documented consumer
        # ceiling (1.5 — fleet_bus.MULT_CEIL), floor unchanged.
        _ceil = getattr(fleet_bus, "MULT_CEIL", 1.5) if fleet_bus else 1.5
        usd = ORDER_USD * max(0.3, min(_ceil, stake_mult))
        # [2026-07-28 AUDIT FIX] re-check the cap with the REAL clip:
        # _entry_blocked gated on flat ORDER_USD but the brain mult can size
        # this entry up to 1.5x — the exact never-count*current-clip class
        # venues/safety.py exists for. Unreachable at today's defaults
        # (3 x $37.50 < $150) but armed the day PARL_ORDER_USD/MAX_OPEN move.
        if self._open_notional() + usd > MAX_NOTIONAL:
            self.last_skip = f"{sym}:notional-cap(mult)"
            return False
        px = self._fill_px(sym, direction > 0)
        if px is None:
            return False
        size = usd / px
        self.broker.open(sym, direction > 0, size, px)
        now = time.time()
        trade_id = f"{self.bot_id}-{sym}-{int(now)}"
        self.open_meta[sym] = {
            "trade_id": trade_id, "opened_ts": now, "tag": tag,
            "entry_px": px, "size": size, "usd": round(usd, 2),
            "features": feats, "p_win": round(p_win, 3),
            "tp": px * (1 + direction * self.params["tp_pct"]),
            "sl": px * (1 - direction * self.params["sl_pct"]),
            "deadline": now + self.params["max_hold_hr"] * 3600.0,
        }
        self.last_entry[sym] = now
        if self.db is not None:
            self.db.record_trade(trade_id, self.base, "parliament", sym,
                                 "long" if direction > 0 else "short", tag,
                                 now, None, px, None, size, None, None, feats)
        if self.bus is not None:
            self.bus.publish("trade.opened", {
                "bot": self.bot_id, "sym": sym, "tag": tag, "px": px,
                "usd": usd, "p_win": p_win})
        log.info("%s OPEN %s %s @%.6g ($%.0f, p=%.2f)", self.bot_id, tag,
                 sym, px, usd, p_win)
        return True

    # -- exits ----------------------------------------------------------------
    def _exit_reason(self, sym: str, meta: dict) -> str | None:
        st = self.data.stats(sym)
        if not st:
            # [2026-07-21 AUDIT FIX] a sym that leaves the market map
            # (delisting / rename / inactive) used to return None HERE,
            # above every exit check — tp/sl/hold/conv/fade/flip all
            # unreachable, so the position sat as a zombie holding a
            # MAX_OPEN slot forever (the Trail-Blazer zombie class,
            # DELIST_GIVEUP_H elsewhere in the fleet). The deadline is
            # data-free, so it stays reachable; past it, close as 'hold'
            # (the broker exits at its last mark — the only price a
            # delisted book has).
            if time.time() >= meta["deadline"]:
                return "hold"
            return None
        px = st["last"] or st["mark"]
        if px <= 0:
            if time.time() >= meta["deadline"]:
                return "hold"
            return None
        direction = 1 if meta["tag"].startswith("long") else -1
        if (px - meta["tp"]) * direction >= 0:
            return "tp"
        if (px - meta["sl"]) * direction <= 0:
            return "sl"
        if time.time() >= meta["deadline"]:
            return "hold"
        if self.strategy == "disloc" and abs(st["prem_bps"]) < 5.0:
            return "conv"
        if self.strategy == "funding":
            apr = (self.data.funding or {}).get(sym)
            if apr is not None and abs(apr) < 5.0:
                return "fade"
        opp = self._fresh_signal(self.primary_topic, sym)
        if opp is not None and opp["direction"] == -direction \
                and opp["strength"] >= 0.6:
            return "flip"
        return None

    def _close(self, sym: str, reason: str) -> None:
        meta = self.open_meta.pop(sym, None)
        if meta is None or sym not in self.broker.pos:
            return
        direction_long = self.broker.pos[sym][0] > 0
        px = self._fill_px(sym, not direction_long)
        if px is None:
            px = self.broker.marks.get(sym, meta["entry_px"])
        pnl = self.broker.close(sym, px)
        # [2026-07-21] grade price + carry together: broker equity already
        # carries fund_acc (accrued into realized as it happened) — the
        # RECORDED pnl adds it once here so the ledger/DB/win-loss call sees
        # the trade the way the book experienced it.
        pnl += float(meta.get("fund_acc") or 0.0)
        if pnl > 0:
            self.wins += 1
        else:
            self.losses += 1
        now = time.time()
        full_tag = f"{meta['tag']}_{reason}"
        if self.db is not None:
            self.db.record_trade(meta["trade_id"], self.base, "parliament",
                                 sym, meta["tag"].split("-")[0], meta["tag"],
                                 meta["opened_ts"], now, meta["entry_px"], px,
                                 meta["size"], pnl, reason, meta["features"])
        if store is not None:
            try:
                store.publish_paper_trade(
                    self.bot_id, meta["trade_id"], round(pnl, 4),
                    pnl_pct=round(pnl / meta["usd"], 6) if meta["usd"] else None,
                    pair=f"{sym}/USD",
                    opened_at=datetime.fromtimestamp(
                        meta["opened_ts"], tz=timezone.utc).isoformat(),
                    closed_at=datetime.fromtimestamp(
                        now, tz=timezone.utc).isoformat(),
                    reason=full_tag, venue="lighter", shadow=True,
                    side=meta["tag"].split("-")[0], tag=full_tag,
                    entry_price=meta["entry_px"], exit_price=px,
                    size=meta["size"],
                    extra={"strategy": self.strategy, "p_win": meta["p_win"],
                           "params": {k: self.params[k] for k in
                                      ("tp_pct", "sl_pct", "max_hold_hr")}})
            except Exception:  # noqa: BLE001
                pass
        if self.bus is not None:
            self.bus.publish("trade.closed", {
                "bot": self.bot_id, "sym": sym, "tag": full_tag,
                "pnl": round(pnl, 4)})
        log.info("%s CLOSE %s %s @%.6g pnl=%+.2f", self.bot_id, full_tag,
                 sym, px, pnl)

    # -- publish --------------------------------------------------------------
    def publish(self) -> None:
        if store is None or self.broker is None:
            return
        eq = self.broker.equity()
        try:
            store.publish(
                self.bot_id, status="online", equity=round(eq, 2),
                pnl_abs=round(eq - START_EQUITY, 2),
                pnl_pct=round(eq / START_EQUITY - 1.0, 6),
                open_trades=len(self.broker.pos),
                closed_trades=self.wins + self.losses,
                wins=self.wins, losses=self.losses,
                pnl_daily=round(self._day_pnl() + self.broker.unrealized(), 2),
                extra={"mode": "lighter_shadow", "strategy": self.strategy,
                       "label": PM_BOTS[self.base][0],
                       "params": {k: round(v, 4) for k, v in self.params.items()},
                       "fund_realized": round(self.fund_realized, 2),
                       # [2026-07-21] the fleet-risk exposure view's held-map
                       # contract ({sym: tag}, tag prefix carries the side)
                       "held": {s: (self.open_meta.get(s) or {}).get(
                                    "tag", "long")
                                for s in self.broker.pos},
                       "last_skip": self.last_skip})
        except Exception:  # noqa: BLE001
            pass
        # [2026-08-15 (my)] I9 MTM series. The MTM_PENDING exemption said the
        # six PM books are "graded by Howard, not by golive_readiness" — that
        # became false when the roster sweep started grading every bot_pnl
        # publisher: pm-albanese and pm-turnbull sit at 2/6 bars in the live
        # payload, graded on realised-only drawdown. The series arms the (ia)
        # worse-of-both bar for them like every other graded holder.
        try:
            store.snapshot_equity(self.bot_id, round(eq, 2),
                                  len(self.broker.pos))
        except Exception:  # noqa: BLE001
            pass

    # -- one cycle ------------------------------------------------------------
    def _accrue_funding(self) -> None:
        """[2026-07-21 AUDIT FIX] Shadow books never accrued funding — the
        Funding Diplomat's ENTIRE edge (received carry) and every book's
        funding drag were invisible to their own P&L, and therefore to the
        ML labels, Howard's grading, and the tuners' replays. Accrue
        per-cycle at the venue's TRUE apr (data.parse_funding, percent):
        positive apr = longs pay shorts (the Farmer's own convention —
        'short_perp if rate > 0' receives). Books equity through
        broker.realized as it accrues; per-position attribution rides
        open_meta['fund_acc'] so _close can grade price+carry together.
        dt capped at 2h so a restart gap never backfills unbounded."""
        now = time.time()
        dt_h = (min(2.0, max(0.0, (now - self._fund_ts) / 3600.0))
                if self._fund_ts else 0.0)
        self._fund_ts = now
        if not dt_h or self.broker is None:
            return
        fund = getattr(self.data, "funding", None) or {}
        for sym, (size, entry) in list(self.broker.pos.items()):
            apr_pct = fund.get(sym)
            if apr_pct is None:
                continue
            mark = self.broker.marks.get(sym) or entry
            notional = abs(size) * mark
            recv = -1.0 if size > 0 else 1.0        # longs pay positive apr
            acc = recv * (float(apr_pct) / 100.0) / 8760.0 * notional * dt_h
            if not acc:
                continue
            self.broker.realized += acc
            self.fund_realized += acc
            meta = self.open_meta.get(sym)
            if meta is not None:
                meta["fund_acc"] = float(meta.get("fund_acc") or 0.0) + acc

    async def cycle(self, effective_params=None) -> None:
        if not self._restored:
            self.restore()
        if effective_params is not None:
            self.params = clamp_params(effective_params)
        await self._ingest()
        if self.broker is None:
            return
        # [2026-07-21 AUDIT FIX] the day used to roll only inside
        # _entry_blocked (i.e. only when candidates existed), so a quiet
        # book published multi-day P&L as "daily" across UTC midnights.
        # Roll unconditionally, every cycle.
        self._day_roll()
        self._accrue_funding()
        # [2026-07-28 AUDIT FIX] ask the candle layer to FOLLOW what this
        # book actually holds: the scanners range over the whole ~215-book
        # map while candles tracked only the 12-book watchlist, so a book
        # like gillard (62 of its last 149 closes off-watchlist) generated
        # closes its own tuner could not replay (silent drop, no counter)
        # and ML candle features read 0.0. track() is bounded + 7d-expiring,
        # so a closed position stays followed exactly as long as the tuner's
        # 7d replay window needs its tape.
        if hasattr(self.data, "track"):
            for sym in list(self.broker.pos):
                self.data.track(sym)
        # mark + exits first — risk comes off before it goes on
        for sym in list(self.broker.pos):
            st = self.data.stats(sym)
            if st and (st["last"] or st["mark"]) > 0:
                self.broker.mark(sym, st["last"] or st["mark"])
            if sym in self.open_meta:
                reason = self._exit_reason(sym, self.open_meta[sym])
                if reason:
                    self._close(sym, reason)
            elif sym not in self.open_meta:
                # position without meta (state drift) — flatten defensively
                self._close_naked(sym)
        for sym, direction, sig in self._candidates():
            self._try_enter(sym, direction, sig)
        self.publish()
        self.save()

    def _close_naked(self, sym: str) -> None:
        st = self.data.stats(sym)
        px = (st["last"] or st["mark"]) if st else None
        if px:
            side_long = self.broker.pos.get(sym, (0.0, 0.0))[0] > 0
            pnl = self.broker.close(sym, px)
            self.losses += 1 if pnl <= 0 else 0
            self.wins += 1 if pnl > 0 else 0
            log.warning("%s flattened meta-less position %s (pnl %+.2f)",
                        self.bot_id, sym, pnl)
            # [2026-07-21 AUDIT FIX] this defensive flatten counted into
            # wins/losses but wrote NO ledger row — the dashboard's closed
            # count drifted permanently ahead of the durable ledger and the
            # brain never saw the close. Record it under its own honest tag.
            now = time.time()
            side = "long" if side_long else "short"
            if self.db is not None:
                try:
                    self.db.record_trade(
                        f"{self.bot_id}-{sym}-naked-{int(now)}", self.base,
                        "parliament", sym, side, side, 0.0, now, px, px,
                        0.0, pnl, "naked_flatten", None)
                except Exception:  # noqa: BLE001
                    pass
            if store is not None:
                try:
                    store.publish_paper_trade(
                        self.bot_id, f"{self.bot_id}-{sym}-naked-{int(now)}",
                        round(pnl, 4), pair=f"{sym}/USD",
                        closed_at=datetime.fromtimestamp(
                            now, tz=timezone.utc).isoformat(),
                        reason=f"{side}_naked_flatten", venue="lighter",
                        shadow=True)
                except Exception:  # noqa: BLE001
                    pass

    async def run_forever(self, interval: float = 60.0, beat=None,
                          params_fn=None):
        while True:
            try:
                eff = params_fn(self.base, base_params(self.strategy, self.base)) \
                    if params_fn else None
                await self.cycle(effective_params=eff)
                if beat:
                    beat(f"bot.{self.base}",
                         f"eq={self.broker.equity():.2f}" if self.broker else "no-broker")
            except Exception as e:  # noqa: BLE001 — one bad cycle never kills a book
                log.exception("%s cycle failed (%s)", self.bot_id, e)
            await asyncio.sleep(interval)


def build_bots(data, bus, db, ml, howard=None) -> list[PMBot]:
    # [(nf)] built through the retirement-aware derivation, never PM_BOTS raw
    from . import live_pm_bots
    return [PMBot(base, strat, data, bus, db, ml, howard)
            for base, (_label, strat) in live_pm_bots().items()]
