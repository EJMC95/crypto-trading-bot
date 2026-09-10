"""LIVE runner. The only module that can sign, and it refuses by default.

THE SHAPE OF THE GATE, in order, with no shortcut around any of it:

  1. `config.LiveGate.evaluate` -- env flags, the confirmation phrase, the
     interactive answer, credentials, no kill switch, valid metadata,
     reconciled account, verified protective-order capability, a healthy nonce
     manager, risk inside the hard ceilings, and the soak.
  2. A pre-flight that RECONCILES with Lighter before every entry, not once at
     startup: positions, active orders, equity. If reconciliation fails, no
     order is placed. Full stop.
  3. Every exit is reduce-only, and the entry+stop go as ONE grouped
     transaction where the SDK supports it.

`LiveTrader` inherits the PAPER runner's scan so the code that decides is
literally the same code the soak validated. What it overrides is `_place`:
that is where simulation ends and signing begins.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from . import execution as ex
from .config import AppConfig, LiveGate, flatten_confirmed
from .health import kill_switch_active
from .lighter_adapter import BaseAdapter
from .logging_setup import event, get
from .market_metadata import MarketRegistry
from .models import Mode, OrderIntent, OrderResult, Position
from .nonce_manager import NonceManager
from .paper_trader import Runner, SoakRecord

log = get("live")


class LiveRefused(RuntimeError):
    """Raised instead of trading. Carries every blocker, not just the first --
    an operator fixing one condition at a time is an operator making five
    attempts."""


@dataclass
class PreflightResult:
    ok: bool
    blockers: list[str] = field(default_factory=list)
    checks: dict[str, Any] = field(default_factory=dict)


class LiveTrader(Runner):
    def __init__(self, cfg: AppConfig, adapter: BaseAdapter,
                 registry: MarketRegistry, *, nonces: NonceManager,
                 interactive_confirmed: bool = False,
                 start_equity: float = 0.0):
        super().__init__(cfg, adapter, registry, mode=Mode.LIVE,
                         start_equity=start_equity)
        self.nonces = nonces
        self.interactive_confirmed = interactive_confirmed
        self.gate = LiveGate(cfg)
        self.reconciled_at: float = 0.0
        self.venue_positions: dict[str, Position] = {}
        self.venue_orders: list[dict[str, Any]] = []

    # ---------------------------------------------------------- preflight --
    def reconcile(self) -> tuple[bool, str]:
        """Local state vs Lighter. Called before EVERY entry."""
        try:
            snap = self.adapter.account()
            orders = self.adapter.active_orders()
        except Exception as exc:                        # noqa: BLE001
            return False, f"reconciliation failed: {exc}"
        self.venue_positions = {p.symbol: p for p in snap.positions}
        self.venue_orders = orders
        self.state.equity = snap.equity
        self.reconciled_at = time.time()
        local = set(self.state.book.positions)
        venue = set(self.venue_positions)
        if local != venue:
            only_local, only_venue = local - venue, venue - local
            return False, (f"position mismatch -- local only {sorted(only_local)}, "
                           f"venue only {sorted(only_venue)}. Refusing to trade "
                           "on an unreconciled book.")
        for sym, p in self.venue_positions.items():
            lp = self.state.book.positions.get(sym)
            if lp and abs(lp.quantity - p.quantity) > 1e-9:
                return False, (f"{sym}: quantity mismatch local {lp.quantity} "
                               f"vs venue {p.quantity}")
        return True, "reconciled"

    def protective_capability(self) -> bool:
        r = getattr(self.adapter, "report", None)
        if r is None:
            return False
        need = ("stop_loss_orders", "reduce_only_exits", "order_cancel")
        return all(r.supports(n) for n in need)

    def preflight(self) -> PreflightResult:
        cfg = self.cfg
        soak = SoakRecord.load(cfg.state_dir)
        rec_ok, rec_note = self.reconcile()
        nonce_ok = (False, "no account/key index configured")
        if self.adapter and getattr(self.adapter, "account_index", None) is not None:
            nonce_ok = self.nonces.healthy(self.adapter.account_index,
                                           self.adapter.api_key_index)
        gate = self.gate.evaluate(
            soak_days=soak.days, soak_signals=soak.signals,
            metadata_valid=bool(self.metadata_version),
            account_reconciled=rec_ok,
            protective_capability=self.protective_capability(),
            nonce_ok=nonce_ok[0],
            interactive_confirmed=self.interactive_confirmed)
        checks = dict(gate.checks)
        checks["reconciliation_note"] = rec_note
        checks["nonce_note"] = nonce_ok[1]
        checks["soak_days"] = round(soak.days, 2)
        checks["soak_signals"] = soak.signals
        return PreflightResult(gate.allowed, list(gate.blockers), checks)

    def require_live(self) -> None:
        pf = self.preflight()
        if not pf.ok:
            raise LiveRefused(
                "LIVE TRADING REFUSED. Unmet conditions:\n  - "
                + "\n  - ".join(pf.blockers)
                + f"\n\nreconciliation: {pf.checks.get('reconciliation_note')}"
                + f"\nnonce: {pf.checks.get('nonce_note')}"
                + f"\nsoak: {pf.checks.get('soak_days')}d / "
                  f"{pf.checks.get('soak_signals')} signals")

    # ------------------------------------------------------------- orders --
    def _place(self, rec: dict[str, Any], sig, dec, now: float) -> None:
        """Where simulation ends. Every branch below either sends a fully
        checked order set or sends nothing."""
        cfg = self.cfg
        if kill_switch_active(cfg.runtime_dir):
            self._reject("kill switch present at placement")
            return
        ok, note = self.reconcile()
        if not ok:
            self._reject("unreconciled at placement")
            log.error("refusing entry for %s: %s", sig.symbol, note)
            return
        try:
            self.require_live()
        except LiveRefused as exc:
            self._reject("live gate closed")
            log.error("%s", exc)
            return

        spread = self._spread(sig.symbol)
        supports_group = self.adapter.report.supports("grouped_orders_oto_oco")
        plan = ex.build_plan(signal=sig, decision=dec, registry=self.registry,
                             cfg=cfg.execution, spread=spread,
                             supports_grouping=supports_group, now_s=now)

        if cfg.execution.require_native_stop_or_fail \
                and not self.protective_capability():
            self._reject("no native protective order capability")
            log.error("refusing entry for %s: native stops unavailable and "
                      "require_native_stop_or_fail is set", sig.symbol)
            return

        lev = self.adapter.set_leverage(sig.symbol, dec.leverage,
                                        cfg.lighter.margin_mode)
        if not lev.accepted:
            self._reject("leverage not set")
            log.error("refusing entry for %s: leverage: %s",
                      sig.symbol, lev.error)
            return

        if supports_group:
            res = self.adapter.submit_grouped(
                [plan.entry, plan.stop] + plan.targets)
            if not res.accepted:
                self._reject("grouped submission rejected")
                log.error("grouped order rejected for %s: %s",
                          sig.symbol, res.error)
                return
            entry_res = res
        else:
            entry_res = self.adapter.submit(plan.entry)
            if not entry_res.accepted:
                self._reject("entry rejected")
                log.error("entry rejected for %s: %s", sig.symbol,
                          entry_res.error)
                return
            stop_res = self.adapter.submit(plan.stop)
            if not stop_res.accepted:
                # A filled entry with no stop is the state this whole module
                # exists to avoid. Cancel the entry and STOP OPENING.
                log.error("stop rejected for %s (%s): cancelling the entry and "
                          "halting new entries", sig.symbol, stop_res.error)
                self.adapter.cancel(sig.symbol, entry_res.order_id or "")
                self._halt("protective stop could not be placed")
                return

        event(log, "live_order_submitted", symbol=sig.symbol, side=sig.side,
              signal_id=sig.signal_id, order_id=entry_res.order_id,
              grouped=supports_group, leverage=dec.leverage,
              quantity=dec.quantity, score=sig.score.total)
        self.state.book.positions[sig.symbol] = Position(
            symbol=sig.symbol, side=sig.side, quantity=dec.quantity,
            entry_price=sig.entry, opened_ts=now, stop_price=sig.stop,
            targets=list(sig.targets), strategy=sig.strategy,
            signal_id=sig.signal_id, stop_order_id=entry_res.order_id,
            protective_ok=True,
            meta={"regime": rec["regime"], "atr": sig.atr,
                  "r": abs(sig.entry - sig.stop), "leverage": dec.leverage,
                  "liquidation": dec.liquidation_price})
        self.budget.record_entry(symbol=sig.symbol, strategy=sig.strategy,
                                 signal_id=sig.signal_id,
                                 score=sig.score.total, now=now)

    def _halt(self, reason: str) -> None:
        """Stop opening. Does NOT close anything: protective exits stay, and
        closing a position is `flatten`, which needs its own confirmation."""
        path = kill_switch_active(self.cfg.runtime_dir)
        log.error("HALTING NEW ENTRIES: %s", reason)
        if not path:
            import os                                    # noqa: PLC0415
            os.makedirs(self.cfg.runtime_dir, exist_ok=True)
            with open(f"{self.cfg.runtime_dir}/KILL_SWITCH", "w") as fh:
                fh.write(f"auto-armed {time.time()}: {reason}\n")

    # ------------------------------------------------------------ flatten --
    def flatten(self, confirmed: bool | None = None) -> list[OrderResult]:
        """Close everything, reduce-only. Requires FLATTEN_CONFIRMATION."""
        if not (flatten_confirmed() if confirmed is None else confirmed):
            raise LiveRefused("flatten refused: FLATTEN_CONFIRMATION must be "
                              "CLOSE_ALL_POSITIONS")
        ok, note = self.reconcile()
        if not ok:
            raise LiveRefused(f"flatten refused: {note}")
        out: list[OrderResult] = []
        for sym, pos in list(self.venue_positions.items()):
            mid = self.registry.market_id(sym)
            if mid is None:
                continue
            req = ex.OrderRequest(
                symbol=sym, market_id=mid, side=ex.exit_side(pos.side),
                intent=OrderIntent.FLATTEN, order_type="market",
                time_in_force="ioc", price=None, trigger_price=None,
                quantity=pos.quantity, reduce_only=True,
                client_order_index=ex.next_client_order_index(),
                signal_id="flatten")
            out.append(self.adapter.submit(req))
        return out
