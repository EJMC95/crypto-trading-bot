"""Live trading: refused by default, and everything here is a way to say no.

THE GATE HAS SEVEN INDEPENDENT LOCKS AND ALL OF THEM MUST BE OPEN:
  1. `mode: live` in the config file;
  2. ENABLE_LIVE_TRADING=true;
  3. LIVE_CONFIRMATION=I_UNDERSTAND_THE_RISK;
  4. an INTERACTIVE confirmation typed at the terminal by a human;
  5. a completed paper soak report from THIS configuration;
  6. a clean reconciliation against the venue;
  7. an adapter that can actually place a reduce-only protective stop.
Plus no KILL_SWITCH file and a configuration inside every hard ceiling.

They are deliberately of different KINDS -- a file, two env vars, a human, an
artefact, a venue read, a capability probe -- because locks of the same kind
fail together. Three env vars would all be defeated by one careless `export`.

NOTHING HERE ENABLES LIVE TRADING AUTOMATICALLY. `main()` cannot be made to
skip the interactive prompt by any argument it accepts; the only bypass in the
whole file is PAPER_SOAK_OVERRIDE, which relaxes lock 5 alone, is recorded in
the gate's own check map, and is printed in the refusal banner so it can never
be used quietly.
"""
from __future__ import annotations

import sys
import time
from typing import Any, Callable

from .config import AppConfig, LiveGate, Mode, validate
from .exchange_adapter import ExchangeAdapter
from .health import kill_switch_active
from .logging_setup import get
from .paper_trader import config_fingerprint, load_report
from .reporting import BAR, render_status
from .store import Store
from .trader import Trader

log = get("live")

CONFIRM_PHRASE = "START LIVE TRADING"


def preflight(cfg: AppConfig, adapter: ExchangeAdapter, *,
              interactive_confirmed: bool = False,
              env: dict[str, str] | None = None) -> tuple[Any, dict[str, Any]]:
    """Evaluate every lock and report. Reads nothing it can write."""
    detail: dict[str, Any] = {}
    rep = load_report(cfg)
    fp = config_fingerprint(cfg)
    same_config = bool(rep and rep.config_fingerprint == fp)
    complete = (False, ["no paper report"])
    if rep:
        complete = rep.complete()
    detail["paper"] = {
        "exists": rep is not None,
        "days": round(rep.days, 2) if rep else 0.0,
        "trades": rep.trades if rep else 0,
        "complete": complete[0],
        "why_incomplete": complete[1],
        "config_fingerprint": rep.config_fingerprint if rep else None,
        "current_fingerprint": fp,
        "same_configuration": same_config,
    }
    if rep and not same_config:
        detail["paper"]["note"] = (
            "the soak was run on a DIFFERENT configuration; it does not "
            "certify this one")

    try:
        positions = adapter.fetch_positions()
        venue_ok = True
    except Exception as exc:                                # noqa: BLE001
        positions, venue_ok = [], False
        detail["venue_error"] = repr(exc)
    from .store import reconcile
    with Store(cfg.state_db) as store:
        rec = reconcile(store, positions) if venue_ok else {"clean": False}
    detail["reconcile"] = rec

    protective = (adapter.capability("native_stop")
                  and adapter.capability("reduce_only")
                  and cfg.execution.use_reduce_only_exits)
    detail["protective_capability"] = protective
    detail["config_problems"] = validate(cfg)
    detail["kill_switch"] = kill_switch_active(cfg.runtime_dir)

    gate = LiveGate(cfg, env=env)
    result = gate.evaluate(
        paper_days=(rep.days if rep and same_config else 0.0),
        paper_trades=(rep.trades if rep and same_config else 0),
        paper_report_exists=bool(rep and same_config),
        paper_checks_passed=bool(complete[0] and same_config),
        account_reconciled=bool(rec.get("clean")),
        protective_capability=protective,
        data_healthy=venue_ok,
        interactive_confirmed=interactive_confirmed)
    return result, detail


def render_gate(result: Any, detail: dict[str, Any], mode: Mode) -> str:
    out = [BAR, "LIVE TRADING GATE", BAR]
    out.append(f"  config mode: {mode.value}")
    for name, ok in sorted(result.checks.items()):
        out.append(f"  [{'OK ' if ok else 'NO '}] {name}")
    p = detail.get("paper", {})
    out.append("")
    out.append(f"  paper soak: {p.get('days', 0):.1f} days, "
               f"{p.get('trades', 0)} trades, "
               f"same configuration: {p.get('same_configuration')}")
    for w in p.get("why_incomplete", []) or []:
        out.append(f"    - {w}")
    if p.get("note"):
        out.append(f"    ! {p['note']}")
    rec = detail.get("reconcile", {})
    out.append(f"  reconciliation: {'clean' if rec.get('clean') else 'NOT CLEAN'}")
    for k in ("orphans", "ghosts", "mismatched", "unprotected"):
        for row in rec.get(k, []) or []:
            out.append(f"    {k[:-1]}: {row}")
    for prob in detail.get("config_problems", []) or []:
        out.append(f"  config problem: {prob}")
    if result.checks.get("paper_soak_overridden_documented"):
        out.append("")
        out.append("  !! PAPER_SOAK_OVERRIDE IS SET. The 30-day soak "
                   "requirement was bypassed by an environment variable. "
                   "This is recorded in the gate's check map and in the "
                   "store's event log.")
    out.append("")
    out.append(f"  VERDICT: {'ALLOWED' if result.allowed else 'REFUSED'}")
    if not result.allowed:
        out.append(f"  blockers: {', '.join(result.blockers)}")
    out.append(BAR)
    return "\n".join(out)


def confirm_interactively(prompt_in: Callable[[str], str] = input,
                          out=sys.stdout) -> bool:
    """Lock 4. A human types a phrase. There is no --yes flag for this, on
    purpose: the whole point of an interactive lock is that it cannot be
    satisfied by something already written down in a script or a systemd unit."""
    out.write("\n" + BAR + "\n")
    out.write("This will place REAL orders with REAL money on a live venue.\n")
    out.write(f"Type exactly: {CONFIRM_PHRASE}\n")
    out.write(BAR + "\n")
    try:
        got = prompt_in("> ")
    except (EOFError, KeyboardInterrupt):
        return False
    ok = got.strip() == CONFIRM_PHRASE
    if not ok:
        out.write("phrase did not match; live trading refused\n")
    return ok


def run_live(cfg: AppConfig, adapter: ExchangeAdapter, *,
             loops: int | None = None, interval_s: float = 60.0,
             prompt_in: Callable[[str], str] = input,
             on_state: Callable[[Any], None] | None = None,
             sleep: Callable[[float], None] = time.sleep,
             env: dict[str, str] | None = None) -> dict[str, Any]:
    """Refuses unless every lock is open. Returns the gate report either way."""
    if cfg.mode is not Mode.LIVE:
        return {"started": False,
                "reason": f"config mode is {cfg.mode.value}, not live"}

    # The interactive lock is evaluated FIRST so a run that is going to be
    # refused for a missing soak does not first ask a human to commit.
    result, detail = preflight(cfg, adapter, interactive_confirmed=False,
                               env=env)
    blockers_before = [b for b in result.blockers
                       if b != "interactive_confirmation"]
    if blockers_before:
        print(render_gate(result, detail, cfg.mode))
        return {"started": False, "reason": "gate refused",
                "blockers": result.blockers, "detail": detail}

    print(render_gate(result, detail, cfg.mode))
    if not confirm_interactively(prompt_in):
        return {"started": False, "reason": "interactive confirmation refused"}

    result, detail = preflight(cfg, adapter, interactive_confirmed=True,
                               env=env)
    if not result.allowed:
        print(render_gate(result, detail, cfg.mode))
        return {"started": False, "reason": "gate refused after confirmation",
                "blockers": result.blockers}

    store = Store(cfg.state_db)
    store.record_event("live_start", {"checks": result.checks,
                                      "detail": detail})
    trader = Trader(cfg, adapter, submit=True, store=store)
    trader.load_markets()
    trader.reconcile_on_start()
    n = 0
    try:
        while loops is None or n < loops:
            st = trader.step()
            n += 1
            if on_state:
                on_state(st)
            else:
                print(render_status(st.as_dict()))
            if kill_switch_active(cfg.runtime_dir):
                log.error("KILL_SWITCH appeared; halting entries and stopping")
                store.record_event("kill_switch_stop", {"loop": n})
                break
            if loops is None or n < loops:
                sleep(interval_s)
    except KeyboardInterrupt:
        log.info("live loop interrupted by operator")
    finally:
        store.record_event("live_stop", {"loops": n})
        store.close()
    return {"started": True, "loops": n}
