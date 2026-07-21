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
    "sl_pct":      (0.005, 0.05),
    "max_hold_hr": (2.0, 96.0),
    "entry_bar":   (0.20, 0.90),
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

    # -- durable state --------------------------------------------------------
    def restore(self) -> None:
        self._restored = True
        if store is None or self.broker is None:
            return
        try:
            st = store.load_state(self.bot_id)
        except Exception:  # noqa: BLE001
            st = None
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
            log.info("%s restored: eq=%.2f open=%d closed=%d",
                     self.bot_id, self.broker.equity(), len(self.broker.pos),
                     self.wins + self.losses)
        except Exception as e:  # noqa: BLE001
            log.warning("%s state restore failed (%s) — fresh book", self.bot_id, e)

    def save(self) -> None:
        if store is None or self.broker is None:
            return
        try:
            store.save_state(self.bot_id, {
                "broker": self.broker.to_state(),
                "wins": self.wins, "losses": self.losses,
                "open_meta": self.open_meta,
                "day": self.day, "day_anchor": self.day_anchor,
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
                # sanity: don't hold against a >2%/day trend just for carry
                if abs(st.get("chg") or 0.0) > 0.10:
                    continue
            out.append((sym, direction, sig))
        return out

    def _try_enter(self, sym: str, direction: int, sig: dict) -> bool:
        why = self._entry_blocked(sym, direction)
        if why:
            self.last_skip = f"{sym}:{why}"
            return False
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
            try:  # the fleet brain's reduce-only per-(bot, tag) multiplier
                stake_mult *= fleet_bus.stake_multiplier(self.bot_id, tag)
            except Exception:  # noqa: BLE001
                pass
        usd = ORDER_USD * max(0.3, min(1.0, stake_mult))
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
            return None
        px = st["last"] or st["mark"]
        if px <= 0:
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
                       "last_skip": self.last_skip})
        except Exception:  # noqa: BLE001
            pass

    # -- one cycle ------------------------------------------------------------
    async def cycle(self, effective_params=None) -> None:
        if not self._restored:
            self.restore()
        if effective_params is not None:
            self.params = clamp_params(effective_params)
        await self._ingest()
        if self.broker is None:
            return
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
            pnl = self.broker.close(sym, px)
            self.losses += 1 if pnl <= 0 else 0
            self.wins += 1 if pnl > 0 else 0
            log.warning("%s flattened meta-less position %s (pnl %+.2f)",
                        self.bot_id, sym, pnl)

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
    return [PMBot(base, strat, data, bus, db, ml, howard)
            for base, (_label, strat) in PM_BOTS.items()]
