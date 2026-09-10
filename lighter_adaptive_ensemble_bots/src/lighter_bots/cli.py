"""Command line. Default mode is BACKTEST; `live` is the only signing path and
it asks twice.

Every command that could reach the venue prints WHAT IT WILL DO before doing
it, and `live` refuses on any unmet condition with the full blocker list.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any

from . import reporting
from .backtester import Backtester, Frictions
from .config import (AppConfig, LIVE_CONFIRMATION_PHRASE, LiveGate, load,
                     validate)
from .data import CandleSource, to_columns
from .health import check as health_check, kill_switch_active
from .lighter_adapter import (MockLighterAdapter, NativeLighterAdapter,
                              build_capability_report)
from .logging_setup import setup
from .market_metadata import MarketRegistry, MetadataStore, discover
from .models import Mode, contained_path
from .paper_trader import Runner, SoakRecord
from .walk_forward import robust, run as wf_run, selection_premium, sensitivity


def _cfg(path: str) -> AppConfig:
    cfg = load(path)
    setup(cfg.log_level)
    for d in (cfg.state_dir, cfg.reports_dir, cfg.runtime_dir, cfg.data_dir):
        os.makedirs(d, exist_ok=True)
    return cfg


def _registry(cfg: AppConfig, offline: bool = False) -> MarketRegistry:
    store = MetadataStore(cfg.data_dir)
    if offline:
        ver, markets, _ts = store.load_latest()
        if not markets:
            raise SystemExit("no cached market metadata; run discover-markets")
        return MarketRegistry(markets, ver or "")
    reg, _ver, _p = discover(cfg.lighter.base_url, cfg.data_dir)
    return reg


def _symbols(cfg: AppConfig, reg: MarketRegistry, top: int = 8) -> list[str]:
    if cfg.symbols:
        return list(cfg.symbols)
    liquid = sorted((m for m in reg.by_symbol.values() if m.complete),
                    key=lambda m: -m.daily_quote_volume)
    return [m.symbol for m in liquid[:top]]


def _load_tapes(cfg: AppConfig, reg: MarketRegistry, symbols: list[str],
                pages: dict[str, int] | None = None
                ) -> dict[str, dict[str, list]]:
    pages = pages or {cfg.timeframes.execution: 6, cfg.timeframes.signal: 6,
                      cfg.timeframes.regime: 4}
    src = CandleSource(cfg.lighter.base_url, cfg.data_dir)
    out: dict[str, dict[str, list]] = {}
    for s in symbols:
        mid = reg.market_id(s)
        if mid is None:
            print(f"  ! {s}: not listed, skipped")
            continue
        by_tf = {}
        for tf in {cfg.timeframes.execution, cfg.timeframes.signal,
                   cfg.timeframes.regime}:
            bars = src.get(s, mid, tf, pages=pages.get(tf, 4))
            by_tf[tf] = bars
        out[s] = by_tf
        print(f"  {s}: " + "  ".join(f"{tf}={len(b)}" for tf, b in
                                     sorted(by_tf.items())))
    return out


def _frictions(cfg: AppConfig) -> Frictions:
    b = cfg.backtest or {}
    return Frictions(
        taker_fee=cfg.execution.taker_fee, maker_fee=cfg.execution.maker_fee,
        spread_bps=float(b.get("spread_bps", 2.0)),
        slippage_bps=float(b.get("slippage_bps", 3.0)),
        funding_per_hour=float(b.get("funding_per_hour", 0.0)),
        post_only_miss_rate=float(b.get("post_only_miss_rate", 0.25)),
        partial_fill_rate=float(b.get("partial_fill_rate", 0.0)),
        partial_fill_fraction=float(b.get("partial_fill_fraction", 0.6)))


# ------------------------------------------------------------- commands -----
def cmd_capabilities(args) -> int:
    cfg = _cfg(args.config) if args.config else AppConfig()
    r = build_capability_report(cfg.lighter.base_url, cfg.lighter.chain_id)
    print(r.render())
    path = os.path.join(cfg.reports_dir, "CAPABILITY_REPORT.txt")
    os.makedirs(cfg.reports_dir, exist_ok=True)
    with open(path, "w") as fh:
        fh.write(r.render() + "\n")
    print(f"\nwritten: {path}")
    return 2 if r.problems else 0


def cmd_discover(args) -> int:
    cfg = _cfg(args.config)
    reg, ver, path = discover(cfg.lighter.base_url, cfg.data_dir)
    complete = [m for m in reg.by_symbol.values() if m.complete]
    print(f"markets: {len(reg)}   complete: {len(complete)}   version: {ver}")
    print(f"snapshot: {path}\n")
    top = sorted(complete, key=lambda m: -m.daily_quote_volume)[:args.top]
    print(f"{'symbol':<10}{'id':>5}{'tick':>12}{'step':>12}{'minQ':>8}"
          f"{'maxLev':>8}{'mmf':>8}{'vol $M':>10}")
    for m in top:
        print(f"{m.symbol:<10}{m.market_id:>5}{m.tick_size:>12g}"
              f"{m.qty_step:>12g}{m.min_quote_amount:>8.0f}"
              f"{m.max_leverage:>7.0f}x{m.maintenance_margin_frac:>8.4f}"
              f"{m.daily_quote_volume / 1e6:>10.1f}")
    incomplete = [m for m in reg.by_symbol.values() if not m.complete]
    if incomplete:
        print(f"\nREFUSED for incomplete metadata: {len(incomplete)} markets"
              f" (e.g. {', '.join(m.symbol for m in incomplete[:6])})")
    return 0


def cmd_validate(args) -> int:
    try:
        cfg = load(args.config)
    except (ValueError, OSError) as exc:
        print(f"INVALID: {exc}")
        return 2
    problems = validate(cfg)
    print(f"config {args.config}: {'OK' if not problems else 'INVALID'}")
    print(f"  mode={cfg.mode.value}  symbols={len(cfg.symbols) or 'auto'}  "
          f"leverage<= {cfg.risk.max_leverage}x  "
          f"risk/trade={cfg.risk.risk_per_trade:.3%}")
    for p in problems:
        print(f"  - {p}")
    return 0 if not problems else 2


def cmd_backtest(args) -> int:
    cfg = _cfg(args.config)
    reg = _registry(cfg, offline=args.offline)
    syms = _symbols(cfg, reg, args.top)
    print(f"symbols: {', '.join(syms)}\nloading tape...")
    tapes = _load_tapes(cfg, reg, syms)
    fr = _frictions(cfg)
    bt = Backtester(cfg, reg, fr, args.equity, cfg.state_dir)
    res = bt.run(tapes, btc_symbol="BTC")
    m = res.metrics()
    print(reporting.backtest_report(
        m, config_note=f"{args.config} | {len(syms)} markets",
        frictions={"taker": fr.taker_fee, "maker": fr.maker_fee,
                   "spread_bps": fr.spread_bps, "slip_bps": fr.slippage_bps,
                   "post_only_miss": fr.post_only_miss_rate}))
    ok, fails = robust(res)
    print(f"\nROBUSTNESS: {'PASS' if ok else 'REFUSED'}")
    for f in fails:
        print(f"  - {f}")
    reporting.write_json(cfg.reports_dir, "backtest.json",
                         {"metrics": m, "robust": ok, "robust_fails": fails,
                          "regime_transitions": res.regime_transitions[-20:]})
    return 0


def cmd_walk_forward(args) -> int:
    cfg = _cfg(args.config)
    reg = _registry(cfg, offline=args.offline)
    syms = _symbols(cfg, reg, args.top)
    tapes = _load_tapes(cfg, reg, syms)
    rep = wf_run(cfg, reg, tapes, train_days=args.train,
                 validate_days=args.validate, test_days=args.test,
                 frictions=_frictions(cfg), start_equity=args.equity)
    print(reporting.walk_forward_report(
        rep.summary(), [{"test": f.test} for f in rep.folds], rep.problems))
    if args.sensitivity:
        grid = {"strategy.long_minimum_score": [56, 62, 68, 74],
                "strategy.short_minimum_score": [56, 62, 68, 74],
                "strategy.adx_threshold": [15, 20, 25],
                "strategy.atr_stop_buffer": [0.0, 0.25, 0.5],
                "strategy.minimum_reward_risk": [1.2, 1.4, 1.8],
                "risk.max_leverage": [2, 5, 8, 10]}
        rows = sensitivity(cfg, reg, tapes, grid, frictions=_frictions(cfg),
                           start_equity=args.equity)
        print(f"\n{'parameter':<36}{'value':>8}{'trades':>8}{'ret%':>10}"
              f"{'sharpe':>9}{'maxDD%':>9}")
        for r in rows:
            print(f"{r['param']:<36}{str(r['value']):>8}{r['trades']:>8}"
                  f"{(r['return_pct'] or 0):>10.3f}{(r['sharpe'] or 0):>9.3f}"
                  f"{(r['max_dd_pct'] or 0):>9.2f}")
        prem = selection_premium(rows)
        if prem:
            print(f"\nSELECTION PREMIUM ({prem['metric']}): best "
                  f"{prem['best']} vs median {prem['median']} over "
                  f"{prem['cells']} cells => +{prem['premium']}")
            print(f"  {prem['note']}")
        reporting.write_json(cfg.reports_dir, "sensitivity.json",
                             {"rows": rows, "selection_premium": prem})
    reporting.write_json(cfg.reports_dir, "walk_forward.json",
                         {"summary": rep.summary(),
                          "problems": rep.problems,
                          "folds": [{"window": f.window.as_dict(),
                                     "validate": f.validate, "test": f.test}
                                    for f in rep.folds]})
    return 0


def _run_loop(cfg: AppConfig, mode: Mode, args) -> int:
    reg = _registry(cfg, offline=args.offline)
    adapter = NativeLighterAdapter(cfg.lighter.base_url, cfg.lighter.chain_id,
                                   allow_signing=False)
    adapter.markets()
    syms = _symbols(cfg, reg, args.top)
    runner = Runner(cfg, adapter, reg, mode=mode, start_equity=args.equity)
    print(f"{mode.value.upper()} on {len(syms)} markets: {', '.join(syms)}")
    print("nothing is signed in this mode.\n")
    for k in range(max(1, args.cycles)):
        out = runner.cycle(syms)
        print(reporting.dashboard(
            mode=mode.value, regime=out["regime"], equity=out["equity"],
            book=out["book"], health=runner.health.snapshot(),
            kill_switch=out["kill_switch"]))
        for o in out["opened"]:
            print(f"  INTENT {o['side'].upper():<5} {o['symbol']:<8} "
                  f"score={o['score']:.1f} rr={o['reward_risk']} "
                  f"qty={o['risk']['quantity']} lev={o['risk']['leverage']}x "
                  f"liq={o['risk']['liquidation_price']}")
        if out["rejections"]:
            print("  rejections: " + ", ".join(
                f"{v}x {k}" for k, v in out["rejections"].items()))
        if mode is Mode.SHADOW and runner.state.shadow_orders:
            reporting.write_json(cfg.reports_dir, "shadow_orders.json",
                                 {"orders": runner.state.shadow_orders})
        if k + 1 < args.cycles:
            time.sleep(args.interval)
    reporting.daily_report(mode.value,
                           {"book": runner.state.book.summary(),
                            "rejections": runner.rejections,
                            "soak": {"days": runner.soak.days,
                                     "signals": runner.soak.signals}},
                           runner.health.snapshot(), cfg.reports_dir)
    return 0


def cmd_paper(args) -> int:
    return _run_loop(_cfg(args.config), Mode.PAPER, args)


def cmd_shadow(args) -> int:
    return _run_loop(_cfg(args.config), Mode.SHADOW, args)


def cmd_health(args) -> int:
    cfg = _cfg(args.config)
    reg = _registry(cfg, offline=args.offline)
    adapter = NativeLighterAdapter(cfg.lighter.base_url, cfg.lighter.chain_id,
                                   allow_signing=False)
    adapter.markets()
    syms = _symbols(cfg, reg, args.top)
    src = CandleSource(cfg.lighter.base_url, cfg.data_dir)
    candles = {s: src.get(s, reg.market_id(s), cfg.timeframes.signal, pages=1)
               for s in syms if reg.market_id(s) is not None}
    store = MetadataStore(cfg.data_dir)
    ver, _m, ts = store.load_latest()
    hc = health_check(runtime_dir=cfg.runtime_dir, metadata_version=ver,
                      metadata_age_s=time.time() - ts if ts else None,
                      candles=candles, timeframe=cfg.timeframes.signal,
                      ws_health=None, nonce_ok=None,
                      account_reconciled=False, regime=None)
    print(hc.render())
    soak = SoakRecord.load(cfg.state_dir)
    print(f"\nSOAK: {soak.days:.2f} days, {soak.signals} signals, "
          f"{soak.orders_planned} orders planned, "
          f"{soak.trades_closed} trades closed")
    gate = LiveGate(cfg).evaluate(soak_days=soak.days, soak_signals=soak.signals,
                                  metadata_valid=bool(ver))
    print(f"LIVE GATE: {'OPEN' if gate.allowed else 'CLOSED'}")
    for b in gate.blockers:
        print(f"  blocked: {b}")
    return 0


def cmd_report(args) -> int:
    cfg = _cfg(args.config) if args.config else AppConfig()
    found = False
    for name in sorted(os.listdir(cfg.reports_dir)):
        if args.date and args.date not in name:
            continue
        print(f"--- {name}")
        # `name` comes from a directory listing, so a symlink in reports/
        # could otherwise read any file the process can. `contained_path`
        # resolves and refuses anything outside the directory.
        try:
            target = contained_path(cfg.reports_dir, name)
        except ValueError as exc:
            print(f"    skipped: {exc}")
            continue
        if name.endswith(".json"):
            try:
                with open(target) as fh:
                    print(json.dumps(json.load(fh), indent=1)[:4000])
            except (OSError, ValueError):
                pass
        else:
            try:
                with open(target) as fh:
                    print(fh.read()[:4000])
            except OSError:
                pass
        found = True
    if not found:
        print("no reports found")
    return 0


def cmd_live(args) -> int:
    cfg = _cfg(args.config)
    if cfg.mode is not Mode.LIVE:
        print(f"config mode is {cfg.mode.value}; `live` needs mode: live")
        return 2
    from .live_trader import LiveRefused, LiveTrader
    from .nonce_manager import NonceManager
    reg = _registry(cfg)
    acct = os.environ.get("LIGHTER_ACCOUNT_INDEX")
    keyi = os.environ.get("LIGHTER_API_KEY_INDEX")
    adapter = NativeLighterAdapter(
        cfg.lighter.base_url, cfg.lighter.chain_id,
        account_index=int(acct) if acct else None,
        api_key_index=int(keyi) if keyi else None,
        signer=None, allow_signing=False)
    try:
        adapter.markets()
    except Exception as exc:                            # noqa: BLE001
        print(f"cannot read market metadata: {exc}")
        return 2
    nonces = NonceManager(cfg.state_dir)
    trader = LiveTrader(cfg, adapter, reg, nonces=nonces,
                        interactive_confirmed=False)
    pre = trader.preflight()
    print("LIVE PRE-FLIGHT")
    for k, v in pre.checks.items():
        print(f"  {k:<32} {v}")
    if not pre.ok:
        print("\nLIVE TRADING REFUSED. Unmet conditions:")
        for b in pre.blockers:
            print(f"  - {b}")
        return 2
    print(f"\nType {LIVE_CONFIRMATION_PHRASE} to confirm live trading, "
          "anything else aborts.")
    try:
        answer = input("> ").strip()
    except (EOFError, KeyboardInterrupt):
        print("aborted")
        return 2
    if answer != LIVE_CONFIRMATION_PHRASE:
        print("aborted: confirmation phrase not given")
        return 2
    trader.interactive_confirmed = True
    try:
        trader.require_live()
    except LiveRefused as exc:
        print(str(exc))
        return 2
    print("live gate OPEN -- but this build ships with adapter signing "
          "DISABLED (allow_signing=False). No transaction will be sent.")
    return 0


def cmd_flatten(args) -> int:
    cfg = _cfg(args.config)
    from .config import FLATTEN_CONFIRMATION_PHRASE, flatten_confirmed
    if not flatten_confirmed():
        print(f"refused: FLATTEN_CONFIRMATION must be "
              f"{FLATTEN_CONFIRMATION_PHRASE}")
        return 2
    print("flatten requires a configured signer; this build ships with "
          "signing disabled. No transaction sent.")
    return 2


def cmd_kill(args) -> int:
    cfg = _cfg(args.config)
    path = os.path.join(cfg.runtime_dir, "KILL_SWITCH")
    if args.clear:
        if os.path.exists(path):
            os.remove(path)
            print(f"removed {path}")
        else:
            print("no kill switch present")
        return 0
    os.makedirs(cfg.runtime_dir, exist_ok=True)
    with open(path, "w") as fh:
        fh.write(f"armed {time.time()}: {args.reason}\n")
    print(f"KILL SWITCH ARMED: {path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="lighter_bots",
        description="Backtest-first long/short ensemble for Lighter. "
                    "Default mode is BACKTEST; live trading is gated.")
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp, need_config: bool = True):
        sp.add_argument("--config", required=need_config)
        sp.add_argument("--offline", action="store_true",
                        help="use the cached metadata snapshot")
        sp.add_argument("--top", type=int, default=8,
                        help="most liquid N markets when symbols is empty")
        return sp

    common(sub.add_parser("capabilities"), False).set_defaults(fn=cmd_capabilities)
    common(sub.add_parser("discover-markets")).set_defaults(fn=cmd_discover)
    sp = sub.add_parser("validate-config")
    sp.add_argument("--config", required=True)
    sp.set_defaults(fn=cmd_validate)

    sp = common(sub.add_parser("backtest"))
    sp.add_argument("--equity", type=float, default=10_000.0)
    sp.set_defaults(fn=cmd_backtest)

    sp = common(sub.add_parser("walk-forward"))
    sp.add_argument("--equity", type=float, default=10_000.0)
    sp.add_argument("--train", type=int, default=180)
    sp.add_argument("--validate", type=int, default=60)
    sp.add_argument("--test", type=int, default=60)
    sp.add_argument("--sensitivity", action="store_true")
    sp.set_defaults(fn=cmd_walk_forward)

    for name, fn in (("paper", cmd_paper), ("shadow", cmd_shadow)):
        sp = common(sub.add_parser(name))
        sp.add_argument("--equity", type=float, default=10_000.0)
        sp.add_argument("--cycles", type=int, default=1)
        sp.add_argument("--interval", type=float, default=60.0)
        sp.set_defaults(fn=fn)

    common(sub.add_parser("health")).set_defaults(fn=cmd_health)

    sp = sub.add_parser("report")
    sp.add_argument("--config", default=None)
    sp.add_argument("--date", default=None)
    sp.set_defaults(fn=cmd_report)

    sp = sub.add_parser("live")
    sp.add_argument("--config", required=True)
    sp.set_defaults(fn=cmd_live)

    sp = sub.add_parser("flatten")
    sp.add_argument("--config", required=True)
    sp.set_defaults(fn=cmd_flatten)

    sp = sub.add_parser("kill-switch")
    sp.add_argument("--config", required=True)
    sp.add_argument("--reason", default="manual")
    sp.add_argument("--clear", action="store_true")
    sp.set_defaults(fn=cmd_kill)

    args = p.parse_args(argv)
    try:
        return int(args.fn(args) or 0)
    except KeyboardInterrupt:
        print("\ninterrupted")
        return 130


if __name__ == "__main__":
    sys.exit(main())
