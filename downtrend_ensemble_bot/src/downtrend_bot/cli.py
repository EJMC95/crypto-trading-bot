"""Command line (spec 17). BACKTEST is the default and nothing else is.

    downtrend backtest       --config config/backtest.yaml
    downtrend walk-forward   --config config/backtest.yaml
    downtrend sensitivity    --config config/backtest.yaml
    downtrend paper          --config config/paper.yaml
    downtrend live           --config config/live.yaml     [refused by default]
    downtrend report         --config config/paper.yaml
    downtrend health         --config config/paper.yaml
    downtrend flatten        --config config/live.yaml     [needs a phrase]
    downtrend validate-config --config config/live.yaml
    downtrend make-examples   --config config/backtest.yaml
    downtrend check-dashboard --feed <url> --before a.py --after b.py

EVERY SUBCOMMAND THAT COULD TOUCH MONEY REFUSES BY DEFAULT and prints why.
`live` cannot be forced from the command line: there is no --yes, and adding
one would defeat the interactive lock it exists to satisfy.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Sequence

from . import config as config_mod
from .backtester import Backtester, Frictions, robustness
from .config import AppConfig, Mode
from .exchange_adapter import CcxtAdapter, MockExchange
from .logging_setup import setup
from .models import Candle
from .reporting import (render_backtest, render_sensitivity, render_status,
                        render_walk_forward, write_json, write_text)


def _load(path: str | None) -> AppConfig:
    if not path:
        return AppConfig()
    return config_mod.load(path)


def _markets(cfg: AppConfig):
    from .synthetic import make_market
    return {s: make_market(s) for s in cfg.symbols}


def _tapes(cfg: AppConfig, args) -> dict[str, dict[str, list[Candle]]]:
    """Real data if a directory was given, synthetic otherwise -- and the
    difference is ANNOUNCED, never inferred from a quiet default."""
    if getattr(args, "data", None):
        return _load_tapes(cfg, args.data)
    from .synthetic import tapes
    print("[synthetic data] no --data directory given. This is a SMOKE TEST "
          "of the machinery, not evidence about any market.", file=sys.stderr)
    return tapes(cfg.symbols, bars_1h=getattr(args, "bars", 1600),
                 seed=getattr(args, "seed", 7))


def _load_tapes(cfg: AppConfig, directory: str
                ) -> dict[str, dict[str, list[Candle]]]:
    """`<dir>/<safe symbol>_<tf>.json`, a list of [ts,o,h,l,c,v] rows."""
    from .models import contained_path, safe_filename
    out: dict[str, dict[str, list[Candle]]] = {}
    tfs = [cfg.timeframes.regime, cfg.timeframes.signal,
           cfg.timeframes.execution]
    for sym in cfg.symbols:
        tape: dict[str, list[Candle]] = {}
        for tf in tfs:
            path = contained_path(directory,
                                  f"{safe_filename(sym)}_{safe_filename(tf)}"
                                  ".json")
            if not os.path.exists(path):
                continue
            with open(path) as fh:
                rows = json.load(fh)
            tape[tf] = [Candle(ts=float(r[0]), open=float(r[1]),
                               high=float(r[2]), low=float(r[3]),
                               close=float(r[4]),
                               volume=float(r[5] if len(r) > 5 else 0.0))
                        for r in rows]
        if tape:
            out[sym] = tape
    if not out:
        raise SystemExit(f"no tapes found under {directory!r} -- expected "
                         "files like BTC_USDT_USDT_1h.json")
    return out


def _frictions(cfg: AppConfig) -> Frictions:
    b = cfg.backtest
    return Frictions(maker_fee=cfg.execution.maker_fee,
                     taker_fee=cfg.execution.taker_fee,
                     spread_bps=b.spread_bps, slippage_bps=b.slippage_bps,
                     funding_per_hour=b.funding_per_hour,
                     limit_miss_rate=b.limit_miss_rate,
                     partial_fill_rate=b.partial_fill_rate,
                     partial_fill_fraction=b.partial_fill_fraction,
                     reject_rate=b.reject_rate)


# ------------------------------------------------------------- commands ----
def cmd_backtest(cfg: AppConfig, args) -> int:
    tapes = _tapes(cfg, args)
    bt = Backtester(cfg, _markets(cfg), frictions=_frictions(cfg),
                    start_equity=cfg.backtest.start_equity)
    res = bt.run(tapes)
    m = res.metrics()
    mc = res.monte_carlo(runs=cfg.backtest.monte_carlo_runs)
    rob = robustness(res)
    text = render_backtest(m, monte_carlo=mc, robust=rob)
    print(text)
    write_json(cfg.reports_dir, "backtest.json",
               {"metrics": m, "monte_carlo": mc,
                "robustness": {"pass": rob[0], "fails": rob[1]},
                "regime_transitions": res.regime_transitions[:50],
                "changepoints": res.changepoints[:50]})
    write_text(cfg.reports_dir, "backtest.txt", text)
    # A REFUSED robustness gate is a non-zero exit: a CI job that runs this
    # must not go green on a configuration the gate rejected.
    return 0 if rob[0] else 2


def cmd_walk_forward(cfg: AppConfig, args) -> int:
    from .walk_forward import walk_forward
    rep = walk_forward(cfg, _markets(cfg), _tapes(cfg, args),
                       train_days=args.train, validate_days=args.validate,
                       test_days=args.test, frictions=_frictions(cfg))
    d = rep.as_dict()
    text = render_walk_forward(d)
    print(text)
    write_json(cfg.reports_dir, "walk_forward.json", d)
    write_text(cfg.reports_dir, "walk_forward.txt", text)
    return 0 if rep.graded else 2


def cmd_sensitivity(cfg: AppConfig, args) -> int:
    """N full backtests, one per swept value. It is SLOW by construction, so
    it prints every cell as it lands -- a sweep that prints nothing for an hour
    is indistinguishable from a sweep that has hung, and the first thing anyone
    does about that is kill it and never run it again."""
    import time as _t

    from .walk_forward import default_grid, sensitivity
    grid = default_grid(cfg)
    grid.pop("_shipped", None)
    if args.only:
        grid = {k: v for k, v in grid.items() if any(o in k for o in args.only)}
        if not grid:
            raise SystemExit(f"--only {args.only} matched no parameter. "
                             f"Known: {', '.join(sorted(default_grid(cfg)))}")
    total = sum(len(v) for v in grid.values()) + 1
    t0 = _t.time()
    done = [0]

    def tick(line: str) -> None:
        done[0] += 1
        el = _t.time() - t0
        eta = (el / done[0]) * (total - done[0]) if done[0] else 0.0
        print(f"  [{done[0]:>3}/{total}] {line}   (elapsed {el / 60:.1f}m, "
              f"~{eta / 60:.1f}m left)", flush=True)

    print(f"sweeping {total} cells across {len(grid)} parameter(s). Each cell "
          f"is a FULL backtest.", flush=True)
    rep = sensitivity(cfg, _markets(cfg), _tapes(cfg, args), grid=grid,
                      frictions=_frictions(cfg), progress=tick)
    text = render_sensitivity(rep)
    print(text)
    write_json(cfg.reports_dir, "sensitivity.json", rep)
    write_text(cfg.reports_dir, "sensitivity.txt", text)
    return 0


def _adapter(cfg: AppConfig, args):
    if cfg.exchange in ("mock", "", None) or getattr(args, "mock", False):
        from .synthetic import make_market, tapes
        t = tapes(cfg.symbols, bars_1h=400)
        return MockExchange(markets=[make_market(s) for s in cfg.symbols],
                            candles={(s, tf): bars
                                     for s, tape in t.items()
                                     for tf, bars in tape.items()},
                            equity=cfg.backtest.start_equity)
    return CcxtAdapter(cfg.exchange,
                       allow_submit=(cfg.mode is Mode.LIVE))


def cmd_paper(cfg: AppConfig, args) -> int:
    from .paper_trader import run_paper
    if cfg.mode is Mode.LIVE:
        print("refusing: this config says mode=live. Use `live`.")
        return 2
    rep = run_paper(cfg, _adapter(cfg, args), loops=args.loops,
                    interval_s=args.interval,
                    on_state=lambda st: print(render_status(st.as_dict())))
    ok, why = rep.complete()
    print(f"\npaper soak: {rep.days:.2f} days, {rep.trades} trades, "
          f"complete={ok}")
    for w in why:
        print(f"  - {w}")
    return 0


def cmd_live(cfg: AppConfig, args) -> int:
    from .live_trader import run_live
    out = run_live(cfg, _adapter(cfg, args), loops=args.loops,
                   interval_s=args.interval)
    if not out.get("started"):
        print(f"\nLIVE TRADING NOT STARTED: {out.get('reason')}")
        return 2
    return 0


def cmd_report(cfg: AppConfig, args) -> int:
    from .store import Store
    with Store(cfg.state_db) as store:
        counts = store.counts()
        trades = store.trades()
        pos = store.open_positions()
        print(json.dumps({"counts": counts, "open_positions": pos,
                          "trades": len(trades),
                          "realised": round(sum(t["pnl"] for t in trades), 2),
                          "recent_decisions": store.decisions(limit=20)},
                         indent=2, default=str))
    return 0


def cmd_health(cfg: AppConfig, args) -> int:
    from .health import StrategyHealthMonitor, kill_switch_active
    mon = StrategyHealthMonitor(cfg.strategy_health, cfg.runtime_dir)
    print(json.dumps({"kill_switch": kill_switch_active(cfg.runtime_dir),
                      "strategies": mon.snapshot()}, indent=2, default=str))
    return 0


def cmd_flatten(cfg: AppConfig, args) -> int:
    """Close everything. Needs FLATTEN_CONFIRMATION=CLOSE_ALL_POSITIONS."""
    if not config_mod.flatten_confirmed():
        print("refusing: set FLATTEN_CONFIRMATION=CLOSE_ALL_POSITIONS")
        return 2
    from .trader import Trader
    adapter = _adapter(cfg, args)
    t = Trader(cfg, adapter, submit=(cfg.mode is Mode.LIVE))
    t.load_markets()
    t.reconcile_on_start()
    out = t.emergency_flatten()
    print(json.dumps(out, indent=2, default=str))
    return 0 if not out.get("errors") else 2


def cmd_validate_config(cfg: AppConfig, args) -> int:
    problems = config_mod.validate(cfg)
    if not problems:
        print(f"config OK (mode={cfg.mode.value}, {len(cfg.symbols)} symbols, "
              f"risk/trade {cfg.risk.risk_per_trade:.3%}, "
              f"max leverage {cfg.risk.max_leverage}x)")
        return 0
    print("CONFIG REFUSED:")
    for p in problems:
        print(f"  - {p}")
    return 2


def cmd_make_examples(cfg: AppConfig, args) -> int:
    """Write a reproducible SYNTHETIC example tape set.

    It exists as a command rather than as committed data because the data is
    generated: shipping megabytes of regenerable JSON in git buys nothing, and
    a reader who runs this gets byte-identical tapes from the same seed."""
    from .models import contained_path, safe_filename
    from .synthetic import tapes

    out_dir = args.out or os.path.join(cfg.data_dir, "examples")
    os.makedirs(out_dir, exist_ok=True)
    t = tapes(cfg.symbols, bars_1h=args.bars, seed=args.seed)
    n = 0
    for sym, tape in t.items():
        for tf, bars in tape.items():
            rows = [[round(c.ts, 3), round(c.open, 8), round(c.high, 8),
                     round(c.low, 8), round(c.close, 8), round(c.volume, 4)]
                    for c in bars]
            path = contained_path(out_dir, f"{safe_filename(sym)}_"
                                           f"{safe_filename(tf)}.json")
            with open(path, "w") as fh:
                json.dump(rows, fh)
            n += 1
    span = 0.0
    first = t[cfg.symbols[0]]["1h"]
    if len(first) > 1:
        span = (first[-1].ts - first[0].ts) / 86400.0
    print(f"wrote {n} SYNTHETIC tapes to {out_dir} "
          f"({len(cfg.symbols)} symbols, {span:.1f} days, seed {args.seed})")
    print("These are GENERATED. A result on them measures the machinery, "
          "not any market.")
    return 0


def cmd_check_dashboard(cfg: AppConfig, args) -> int:
    from .dashboard_safety import certify
    def _read(path: str | None, fallback: str = "") -> str:
        if not path:
            return fallback
        with open(path) as fh:          # closed on every path, including raise
            return fh.read()

    before = _read(args.before)
    after = _read(args.after, before)
    out = certify(feed_url=args.feed, before_src=before, after_src=after,
                  new_bot_ids=(args.bot or []))
    print(json.dumps(out, indent=2, default=str))
    return 0 if out.get("allowed") else 2


# ---------------------------------------------------------------- parser ---
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="downtrend",
                                description=__doc__.splitlines()[0])
    p.add_argument("--config", default=None)
    p.add_argument("--log-level", default=None)
    sub = p.add_subparsers(dest="cmd")

    def data_args(sp):
        sp.add_argument("--data", default=None,
                        help="directory of <SYMBOL>_<tf>.json tapes; "
                             "omitted means SYNTHETIC data")
        sp.add_argument("--bars", type=int, default=1600)
        sp.add_argument("--seed", type=int, default=7)

    b = sub.add_parser("backtest"); data_args(b)
    w = sub.add_parser("walk-forward"); data_args(w)
    w.add_argument("--train", type=int, default=180)
    w.add_argument("--validate", type=int, default=60)
    w.add_argument("--test", type=int, default=60)
    s = sub.add_parser("sensitivity"); data_args(s)
    s.add_argument("--only", action="append",
                   help="sweep only parameters whose path contains this "
                        "(repeatable). The full grid is ~41 full backtests.")

    for name in ("paper", "live"):
        sp = sub.add_parser(name)
        sp.add_argument("--loops", type=int, default=None)
        sp.add_argument("--interval", type=float, default=60.0)
        sp.add_argument("--mock", action="store_true")
    sub.add_parser("report")
    sub.add_parser("health")
    f = sub.add_parser("flatten"); f.add_argument("--mock", action="store_true")
    sub.add_parser("validate-config")
    e = sub.add_parser("make-examples")
    e.add_argument("--out", default=None)
    e.add_argument("--bars", type=int, default=4000)
    e.add_argument("--seed", type=int, default=11)
    d = sub.add_parser("check-dashboard")
    d.add_argument("--feed", required=True)
    d.add_argument("--before")
    d.add_argument("--after")
    d.add_argument("--bot", action="append")
    return p


COMMANDS = {
    "backtest": cmd_backtest, "walk-forward": cmd_walk_forward,
    "sensitivity": cmd_sensitivity, "paper": cmd_paper, "live": cmd_live,
    "report": cmd_report, "health": cmd_health, "flatten": cmd_flatten,
    "validate-config": cmd_validate_config,
    "make-examples": cmd_make_examples,
    "check-dashboard": cmd_check_dashboard,
}


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.cmd:
        build_parser().print_help()
        return 1
    try:
        cfg = _load(args.config)
    except (ValueError, OSError) as exc:
        # `config.load` refuses a file that breaches a ceiling, which is
        # correct and fail-closed. Letting that reach the terminal as a
        # traceback is not: an operator reading a stack trace at 3am cannot
        # tell a rejected setting from a crashed program.
        print("CONFIG REFUSED (nothing runs on a configuration that breaches "
              "a hard ceiling):")
        for line in str(exc).splitlines():
            print(f"  {line}")
        return 2
    setup(level=(args.log_level or cfg.log_level))
    if args.cmd not in ("validate-config", "check-dashboard"):
        problems = config_mod.validate(cfg)
        if problems:
            print("CONFIG REFUSED (nothing runs on a configuration that "
                  "breaches a hard ceiling):")
            for p in problems:
                print(f"  - {p}")
            return 2
    return COMMANDS[args.cmd](cfg, args)


if __name__ == "__main__":
    raise SystemExit(main())
