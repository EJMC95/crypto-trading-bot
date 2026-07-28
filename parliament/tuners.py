#!/usr/bin/env python3
"""
parliament/tuners.py — Layer 5: six tuner bots, one per PM book.

The self-evolution loop, built on the fleet's growth-rail doctrine
(lighter_scout_tuner is the parent): REPLAY-GATED, BOUNDED, TTL'd,
AUTO-REVERTING, and EPISODE-GRADED after the fact.

Each tuner, hourly, for its bot:
  1. REPLAY — every closed trade from the ecosystem DB is re-simulated
     against the stored candle tape with candidate TP/SL/hold variants.
     Baseline and variant run through the SAME simulator (never variant-sim
     vs recorded-actual — that comparison is polluted by fills).
  2. ANTI-OVERFIT FLOORS — a variant enacts only with >= 10 replayable
     closes, a total improvement >= $2, AND improvement on BOTH halves of
     the window (the scout tuner's not-worse-both-halves bar).
  3. ONE lever per bot per cycle, clamped to PARAM_BOUNDS, TTL 6h —
     expiry reverts to baseline; re-assertion must re-earn the bar.
  4. PROPRIOCEPTION-LITE — when a lever's last graded episode for
     (bot, param) says 'hurting', the tuner REFUSES to re-assert it
     (restrict-first: a movement that measured bad stops being repeated).
  5. STARVING FALLBACK — a book with < 5 closes/7d gets one bounded
     entry_bar widening (grading diet: more trades to learn from), never
     stacked with a performance lever in the same cycle.
  6. EPISODE GRADING — ended levers are graded out-of-sample: per-trade
     P&L during the episode vs the bot's surrounding window. helping /
     hurting / neutral with floors (n >= 5, |delta| >= $2), written back to
     the ecosystem DB where rule 4 and Howard read it.

Zero real money anywhere near this: every book is shadow, every lever is a
shadow-book parameter, and PARAM_BOUNDS is the hard cage.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time

from .strategies import PARAM_BOUNDS, clamp_params
from .data import RES_FAST

log = logging.getLogger("parliament.tuners")

TUNE_INTERVAL_SEC = float(os.environ.get("PARL_TUNE_INTERVAL_SEC", "3600"))
LEVER_TTL_SEC = float(os.environ.get("PARL_LEVER_TTL_SEC", "21600"))   # 6h
MIN_REPLAY_TRADES = int(os.environ.get("PARL_TUNE_MIN_TRADES", "10"))
# [2026-07-28] per-half floor on REPLAYABLE trades — without it a half with
# zero replayables passed the both-halves gate trivially (0.0 >= 0.0).
MIN_HALF_REPLAY = int(os.environ.get("PARL_TUNE_MIN_HALF", "3"))
MIN_IMPROVE_USD = float(os.environ.get("PARL_TUNE_MIN_IMPROVE_USD", "2.0"))
STARVING_CLOSES_7D = int(os.environ.get("PARL_STARVING_CLOSES_7D", "5"))
GRADE_MIN_TRADES = 5
GRADE_MIN_DELTA_USD = 2.0

# single-param candidate walks (mult applied to the current baseline value)
SWEEP = [("tp_pct", 0.75), ("tp_pct", 1.25),
         ("sl_pct", 0.75), ("sl_pct", 1.25),
         ("max_hold_hr", 0.5), ("max_hold_hr", 1.5)]


def simulate_exit(direction: int, entry_px: float, opened_ts: float,
                  candles: list[dict], tp_pct: float, sl_pct: float,
                  max_hold_hr: float) -> tuple[float, str] | None:
    """Walk the candle tape from entry; SL checks before TP inside a bar
    (conservative). Returns (exit_px, reason) or None when the tape can't
    cover the trade (caller must then drop the trade from BOTH arms)."""
    tp = entry_px * (1 + direction * tp_pct)
    sl = entry_px * (1 - direction * sl_pct)
    deadline = opened_ts + max_hold_hr * 3600.0
    bars = [b for b in candles if b["t"] >= opened_ts]
    if not bars:
        return None
    for b in bars:
        if direction > 0:
            if b["l"] <= sl:
                return sl, "sl"
            if b["h"] >= tp:
                return tp, "tp"
        else:
            if b["h"] >= sl:
                return sl, "sl"
            if b["l"] <= tp:
                return tp, "tp"
        if b["t"] >= deadline:
            return b["c"], "hold"
    return bars[-1]["c"], "open"     # tape ends mid-trade: mark at last close


def replay_pnl_usd(trade: dict, candles: list[dict], tp_pct: float,
                   sl_pct: float, max_hold_hr: float) -> float | None:
    direction = 1 if (trade.get("side") or "").startswith("long") else -1
    entry = trade.get("entry_px")
    size = trade.get("size")
    if not entry or not size:
        return None
    sim = simulate_exit(direction, entry, trade["opened_ts"], candles,
                        tp_pct, sl_pct, max_hold_hr)
    if sim is None:
        return None
    exit_px, _reason = sim
    return direction * size * (exit_px - entry)


class TunerBench:
    def __init__(self, db, bus=None, data=None):
        self.db = db
        self.bus = bus
        self.data = data
        self.cycles = 0
        self.enacted = 0
        # [2026-07-28] per-bot replay coverage (n7d vs with_tape) — tape
        # starvation as a number, not a silent continue
        self.coverage: dict = {}

    # -- the read side bots use every cycle -----------------------------------
    def effective_params(self, bot: str, base: dict) -> dict:
        """Base params with this bot's ACTIVE levers overlaid, clamped. An
        expired lever simply stops appearing — auto-revert is the resting
        state (fleet_tuning semantics)."""
        p = dict(base)
        if self.db is None:
            return clamp_params(p)
        try:
            for lever in self.db.active_levers(bot):
                if lever["param"] in PARAM_BOUNDS:
                    p[lever["param"]] = lever["value"]
        except Exception:  # noqa: BLE001
            pass
        return clamp_params(p)

    # -- proprioception-lite --------------------------------------------------
    def _last_verdict(self, bot: str, param: str,
                      max_age_sec: float = 7 * 86400) -> str | None:
        """[2026-07-21 AUDIT FIX] verdicts now AGE OUT (default 7d from the
        episode's end). The old any-age read made a 'hurting' PERMANENT: the
        hurting refusal blocks new levers on that (bot,param), new verdicts
        only come from new levers, so nothing could ever supersede the
        blacklist — the exact opposite of the fleet's proprioception
        contract, where a stale organ restricts nothing."""
        try:
            hist = self.db.lever_history(bot, param, limit=3)
        except Exception:  # noqa: BLE001
            return None
        now = time.time()
        for h in hist:
            if h.get("verdict") in ("helping", "hurting", "neutral"):
                ended = h.get("released_ts") or h.get("expires_ts") or 0
                if ended and now - ended > max_age_sec:
                    return None      # newest conclusive verdict is stale
                return h["verdict"]
        return None

    # -- the hourly cycle for one bot -----------------------------------------
    # [2026-07-21 AUDIT FIX] default resolution follows the data layer's
    # RES_FAST — the hardcoded '15m' meant a PARL_RES_FAST override stored
    # candles under one key while every replay read another: empty tapes,
    # replay_pnl_usd None for every trade, all performance tuning silently off.
    def tune_bot(self, bot: str, base: dict,
                 resolution: str = RES_FAST) -> dict | None:
        self.cycles += 1
        self.grade_episodes(bot)
        if self.db is None:
            return None
        if self.db.active_levers(bot):
            return None      # one lever at a time; let the episode finish
        trades = [t for t in self.db.closed_trades(bot=bot, days=7.0)
                  if t.get("source") == "parliament"]
        if len(trades) < STARVING_CLOSES_7D:
            return self._starving_widen(bot, base)
        if len(trades) < MIN_REPLAY_TRADES:
            return None
        trades.sort(key=lambda t: t["closed_ts"] or 0)
        tapes = {}
        for t in trades:
            sym = t["sym"]
            if sym not in tapes:
                tapes[sym] = self.db.get_candles(sym, resolution, limit=2000)
        # [2026-07-28 AUDIT FIX] replay COVERAGE is now a visible number —
        # tape starvation used to be a silent `continue` (measured: ~40% of
        # gillard's closes off the candled watchlist, dropped invisibly).
        self.coverage[bot] = {
            "n7d": len(trades),
            "with_tape": sum(1 for t in trades if tapes.get(t["sym"]))}
        cur = clamp_params(base)
        best = None
        for param, mult in SWEEP:
            if self._last_verdict(bot, param) == "hurting":
                continue
            lo, hi = PARAM_BOUNDS[param]
            value = max(lo, min(hi, cur[param] * mult))
            if abs(value - cur[param]) < 1e-9:
                continue
            variant = dict(cur, **{param: value})
            # [2026-07-28 AUDIT FIX] split by REPLAYABLE index with a
            # per-half floor. The old split indexed over ALL trades and had
            # no per-half n floor, so 0.0 >= 0.0 passed a half that
            # contributed ZERO replayable trades — and tape coverage is
            # watchlist-biased, so replayables genuinely cluster: a variant
            # could clear the both-halves doctrine bar on what was
            # effectively a one-half, in-sample read (the fleet's
            # episodes-not-trades honest-denominator rule, applied here).
            pairs = []
            for t in trades:
                tape = tapes.get(t["sym"]) or []
                b = replay_pnl_usd(t, tape, cur["tp_pct"], cur["sl_pct"],
                                   cur["max_hold_hr"])
                v = replay_pnl_usd(t, tape, variant["tp_pct"],
                                   variant["sl_pct"], variant["max_hold_hr"])
                if b is None or v is None:
                    continue     # dropped from BOTH arms — fair comparison
                pairs.append((b, v))
            n = len(pairs)
            if n < MIN_REPLAY_TRADES:
                continue
            half = n // 2
            if half < MIN_HALF_REPLAY or (n - half) < MIN_HALF_REPLAY:
                continue
            base_h1 = sum(b for b, _ in pairs[:half])
            var_h1 = sum(v for _, v in pairs[:half])
            base_h2 = sum(b for b, _ in pairs[half:])
            var_h2 = sum(v for _, v in pairs[half:])
            improve = (var_h1 + var_h2) - (base_h1 + base_h2)
            if improve >= MIN_IMPROVE_USD and var_h1 >= base_h1 \
                    and var_h2 >= base_h2:
                if best is None or improve > best["improve"]:
                    best = {"param": param, "value": value,
                            "baseline": cur[param],
                            "improve": round(improve, 2), "n": n}
        if best is None:
            return None
        return self._enact(bot, best, note=f"replay +${best['improve']}"
                                           f" on n={best['n']}")

    def _starving_widen(self, bot: str, base: dict) -> dict | None:
        """< STARVING closes in 7d: one bounded entry_bar widening so the
        book generates gradeable evidence (the scout tuner's grading-diet
        move). Never repeats while an episode is active or graded hurting."""
        if self._last_verdict(bot, "entry_bar") == "hurting":
            return None
        cur = clamp_params(base)
        lo, _hi = PARAM_BOUNDS["entry_bar"]
        value = max(lo, cur["entry_bar"] * 0.85)
        if abs(value - cur["entry_bar"]) < 1e-9:
            return None
        return self._enact(bot, {"param": "entry_bar", "value": value,
                                 "baseline": cur["entry_bar"]},
                           note="starving: <%d closes/7d" % STARVING_CLOSES_7D)

    def _enact(self, bot: str, lever: dict, note: str) -> dict:
        lid = self.db.open_lever(bot, lever["param"], lever["value"],
                                 lever["baseline"], LEVER_TTL_SEC, note)
        self.enacted += 1
        payload = {"bot": bot, "lever_id": lid, "param": lever["param"],
                   "value": round(lever["value"], 5),
                   "baseline": round(lever["baseline"], 5),
                   "ttl_sec": LEVER_TTL_SEC, "note": note}
        if self.bus is not None:
            self.bus.publish("tuning.applied", payload)
        log.info("%s-tuner ENACT %s=%.5g (was %.5g, ttl %.0fh) — %s", bot,
                 lever["param"], lever["value"], lever["baseline"],
                 LEVER_TTL_SEC / 3600.0, note)
        return payload

    # -- retrospective episode grading ---------------------------------------
    def grade_episodes(self, bot: str) -> int:
        """Grade ended, ungraded levers: per-trade P&L during the episode vs
        the bot's per-trade P&L in the surrounding 7d window (out-of-sample
        for the enactment decision, which was made on REPLAY numbers)."""
        if self.db is None:
            return 0
        graded = 0
        now = time.time()
        # lever_history is per-param; walk every param this bench governs.
        for param in PARAM_BOUNDS:
            for h in self.db.lever_history(bot, param, limit=5):
                ended = h["released_ts"] or (
                    h["expires_ts"] if h["expires_ts"] < now else None)
                if not ended:
                    continue
                # [2026-07-21 AUDIT FIX] 'insufficient' is no longer frozen
                # forever: while the episode's 14d evidence window is still
                # open, re-examine it each pass — trades that closed AFTER
                # the first look can upgrade it to a real verdict. Conclusive
                # verdicts stay final.
                verdict_now = h.get("verdict")
                if verdict_now and not (verdict_now == "insufficient"
                                        and now - ended <= 14 * 86400):
                    continue
                trades = self.db.closed_trades(bot=bot, days=14.0)
                inside = [t["pnl_abs"] for t in trades
                          if t["pnl_abs"] is not None
                          and h["applied_ts"] <= (t["closed_ts"] or 0) <= ended]
                outside = [t["pnl_abs"] for t in trades
                           if t["pnl_abs"] is not None
                           and not (h["applied_ts"] <= (t["closed_ts"] or 0)
                                    <= ended)]
                if len(inside) < GRADE_MIN_TRADES or len(outside) < GRADE_MIN_TRADES:
                    if verdict_now != "insufficient":
                        self.db.grade_lever(h["id"], "insufficient")
                        graded += 1
                    continue
                delta = (sum(inside) / len(inside)
                         - sum(outside) / len(outside)) * len(inside)
                verdict = "helping" if delta >= GRADE_MIN_DELTA_USD else \
                          "hurting" if delta <= -GRADE_MIN_DELTA_USD else \
                          "neutral"
                self.db.grade_lever(h["id"], verdict)
                graded += 1
                log.info("%s-tuner GRADE lever#%s %s=%s -> %s (Δ$%.2f on n=%d)",
                         bot, h["id"], param, h["value"], verdict, delta,
                         len(inside))
        return graded

    # -- reporting for Howard -------------------------------------------------
    def snapshot(self) -> dict:
        out = {"cycles": self.cycles, "enacted": self.enacted, "active": {},
               "replay_coverage": dict(self.coverage)}
        if self.db is not None:
            try:
                for lever in self.db.active_levers():
                    out["active"].setdefault(lever["bot"], []).append(
                        {"param": lever["param"],
                         "value": round(lever["value"], 5),
                         "expires_in_sec": int(lever["expires_ts"] - time.time())})
            except Exception:  # noqa: BLE001
                pass
        return out

    async def run_forever(self, bots: list, interval: float = TUNE_INTERVAL_SEC,
                          beat=None):
        """One bench task tunes all six books, staggered inside the hour."""
        from .strategies import base_params
        stagger = interval / max(1, len(bots))
        while True:
            for bot in bots:
                try:
                    self.tune_bot(bot.base,
                                  base_params(bot.strategy, bot.base))
                    # [2026-07-28 AUDIT FIX] beat INSIDE the try — outside
                    # it, a tune_bot throwing every cycle still beat 'ok'
                    # hourly forever (loud in the log, invisible to Howard,
                    # whose whole job is noticing exactly this). The bots'
                    # own run_forever is the precedent.
                    if beat:
                        beat(f"tuner.{bot.base}", "ok")
                except Exception as e:  # noqa: BLE001
                    log.exception("%s-tuner cycle failed (%s)", bot.base, e)
                await asyncio.sleep(stagger)
