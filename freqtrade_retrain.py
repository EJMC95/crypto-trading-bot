#!/usr/bin/env python3
"""
freqtrade_retrain.py — autonomous "learn from live data" loop for the Freqtrade bots.

WHAT IT DOES (per strategy, on a schedule):
  1. Downloads the most recent Kraken OHLCV (the same live data the bots trade on).
  2. Runs a bounded hyperopt over a TRAIN window to find candidate parameters.
  3. Backtests BOTH the candidate and the current ("incumbent") params on a
     held-out RECENT window the optimiser never saw.
  4. Promotes the candidate ONLY if it beats the incumbent out-of-sample
     (more profit AND drawdown not materially worse AND enough trades).
  5. If promotion is enabled (GITHUB_TOKEN + RETRAIN_PROMOTE=true) it commits the
     winning user_data/strategies/<Strategy>.json back to GitHub, which triggers
     Railway to redeploy the live freqtrade-bots service with the new params.
     Otherwise it runs in SHADOW mode: it logs what it *would* promote and changes
     nothing live. This is the safe default.

Everything stays dry-run / paper. This script never places an order or moves money.
It only tunes existing strategy parameters and is designed to be conservative:
regime/trend safety parameters are intentionally left non-optimisable in the
strategies, so optimisation cannot loosen the core risk controls.

Runs inside the freqtradeorg/freqtrade image (freqtrade + hyperopt preinstalled).
Standard library only (plus the freqtrade CLI invoked as a subprocess).
"""

import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

# --------------------------------------------------------------------------- #
# Config (all overridable via env)
# --------------------------------------------------------------------------- #
REPO_SLUG       = os.environ.get("GIT_REPO_SLUG", "EJMC95/crypto-trading-bot")
GIT_BRANCH      = os.environ.get("GIT_BRANCH", "main")
GITHUB_TOKEN    = os.environ.get("GITHUB_TOKEN", "").strip()
PROMOTE         = os.environ.get("RETRAIN_PROMOTE", "false").lower() == "true"

INTERVAL_HOURS  = float(os.environ.get("RETRAIN_INTERVAL_HOURS", "48"))
EPOCHS          = int(os.environ.get("RETRAIN_EPOCHS", "60"))
PAIRS           = os.environ.get("RETRAIN_PAIRS", "BTC/USD ETH/USD").split()
TRAIN_DAYS      = int(os.environ.get("RETRAIN_TRAIN_DAYS", "35"))
HOLDOUT_DAYS    = int(os.environ.get("RETRAIN_HOLDOUT_DAYS", "10"))
# Extra history downloaded BEFORE the train window so the strategies' long EMAs
# (SwingDip 200x4h ~33d, Momo 260x4h ~43d) have their startup candles available.
STARTUP_DAYS    = int(os.environ.get("RETRAIN_STARTUP_DAYS", "50"))
HYPEROPT_LOSS   = os.environ.get("RETRAIN_LOSS", "SharpeHyperOptLossDaily")
JOBS            = os.environ.get("RETRAIN_JOBS", "1")           # bound CPU on Railway
MIN_TRADES      = int(os.environ.get("RETRAIN_MIN_TRADES", "4"))  # need evidence to promote
DD_TOLERANCE    = float(os.environ.get("RETRAIN_DD_TOLERANCE", "0.03"))  # +3pp DD allowed
RUN_ONCE        = os.environ.get("RETRAIN_ONCE", "false").lower() == "true"
# Kraken serves no historical OHLCV — only raw trades — so we download trades and
# resample. DATADIR should point at a persistent Railway volume so downloads are
# incremental (first cycle slow, later cycles only fetch the delta).
DATADIR         = os.environ.get("RETRAIN_DATADIR", "").strip()

# strategy -> (config file, timeframes to download incl. informative/regime)
STRATEGIES = {
    "SwingDipV1":     ("config_v6_swing.json", ["4h", "1d"]),
    "MomoBreakoutV1": ("config_v7_momo.json",  ["4h", "1d"]),
}
# Intentionally omitted:
#  - ImprovedStrategyV4: exposes no tunable parameters (nothing to optimise).
#  - DayTraderV5Gated: its 1d EMA200 regime filter needs ~200 days of daily
#    candles; Kraken serves no historical OHLCV, so that would require
#    downloading ~200 days of raw trades (millions) per cycle — not feasible.
#    It keeps trading live on its current (now regime-gated) rules.
# The 4h strategies need ~35-45 days of history (≈200x4h startup candles), which
# is a tractable trades download and is what RETRAIN_TRAIN_DAYS defaults target.


def log(msg):
    print(f"[retrain {datetime.now(timezone.utc):%Y-%m-%dT%H:%M:%SZ}] {msg}", flush=True)


def run(cmd, cwd, timeout=5400):
    """Run a command, stream nothing, return (rc, stdout+stderr)."""
    log("$ " + " ".join(cmd))
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"
    out = (p.stdout or "") + (p.stderr or "")
    # Show the tail so Railway logs stay readable.
    tail = "\n".join(out.splitlines()[-12:])
    if tail:
        print(tail, flush=True)
    return p.returncode, out


def workdir_setup():
    """Return the working dir. Clone fresh if we have a token (so we can push and
    always run the latest strategies); otherwise use the baked-in /app copy."""
    if GITHUB_TOKEN:
        wd = "/tmp/repo"
        shutil.rmtree(wd, ignore_errors=True)
        url = f"https://x-access-token:{GITHUB_TOKEN}@github.com/{REPO_SLUG}.git"
        rc, _ = run(["git", "clone", "--depth", "1", "-b", GIT_BRANCH, url, wd], cwd="/tmp")
        if rc != 0:
            log("clone failed; falling back to baked-in /app copy (shadow only)")
            return "/app", False
        run(["git", "config", "user.email", "retrainer@bots.local"], cwd=wd)
        run(["git", "config", "user.name", "freqtrade-retrainer"], cwd=wd)
        return wd, True
    return "/app", False


def timeranges():
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=TRAIN_DAYS + HOLDOUT_DAYS)
    holdout_start = now - timedelta(days=HOLDOUT_DAYS)
    train = f"{start:%Y%m%d}-{holdout_start:%Y%m%d}"
    holdout = f"{holdout_start:%Y%m%d}-{now:%Y%m%d}"
    return train, holdout


def read_backtest_metrics(wd, strat):
    """Parse the latest backtest result for `strat`. Returns dict or None."""
    last = os.path.join(wd, "user_data", "backtest_results", ".last_result.json")
    try:
        with open(last) as f:
            latest = json.load(f)["latest_backtest"]
        with open(os.path.join(wd, "user_data", "backtest_results", latest)) as f:
            data = json.load(f)
        s = data["strategy"][strat]
        return {
            "profit_total": float(s.get("profit_total", 0.0)),          # fraction
            "max_drawdown": float(s.get("max_drawdown_account",
                                        s.get("max_drawdown", 0.0))),    # fraction
            "trades": int(s.get("total_trades", 0)),
        }
    except Exception as e:  # noqa: BLE001
        log(f"could not read backtest metrics for {strat}: {e}")
        return None


def datadir_for(wd):
    return DATADIR if DATADIR else os.path.join(wd, "user_data", "data")


def write_override(wd):
    """Backtesting/hyperopt don't support VolumePairList/AgeFilter (live-only),
    so emit a small config that forces a StaticPairList over our chosen pairs.
    Passed as a second --config; freqtrade deep-merges it over the base config."""
    path = os.path.join(wd, "_retrain_override.json")
    with open(path, "w") as f:
        json.dump({
            "pairlists": [{"method": "StaticPairList"}],
            "exchange": {"pair_whitelist": PAIRS},
        }, f)
    return path


def _dd_args(wd):
    return ["--datadir", datadir_for(wd)]


def backtest(wd, cfg, ovr, strat, holdout):
    run(["freqtrade", "backtesting", "--config", cfg, "--config", ovr,
         "--strategy", strat, "--timerange", holdout, "-p", *PAIRS,
         "--cache", "none", *_dd_args(wd)], cwd=wd)
    return read_backtest_metrics(wd, strat)


def better(cand, inc):
    """Out-of-sample promotion rule."""
    if cand is None or cand["trades"] < MIN_TRADES:
        return False, f"candidate has too few trades ({cand['trades'] if cand else 'n/a'} < {MIN_TRADES})"
    if inc is None:
        return cand["profit_total"] > 0, "no incumbent metrics; promote only if candidate is profitable"
    if cand["profit_total"] <= inc["profit_total"]:
        return False, (f"candidate profit {cand['profit_total']:.4f} "
                       f"not above incumbent {inc['profit_total']:.4f}")
    if cand["max_drawdown"] > inc["max_drawdown"] + DD_TOLERANCE:
        return False, (f"candidate drawdown {cand['max_drawdown']:.4f} worse than "
                       f"incumbent {inc['max_drawdown']:.4f} + {DD_TOLERANCE}")
    return True, (f"candidate better: profit {cand['profit_total']:.4f} vs "
                  f"{inc['profit_total']:.4f}, DD {cand['max_drawdown']:.4f} vs "
                  f"{inc['max_drawdown']:.4f}")


def retrain_one(wd, can_push, strat, cfg_name, tfs, train, holdout):
    log(f"===== {strat} ({cfg_name}) =====")
    cfg = os.path.join(wd, cfg_name)
    ovr = write_override(wd)
    sdir = os.path.join(wd, "user_data", "strategies")
    pfile = os.path.join(sdir, f"{strat}.json")           # the params file the live bot loads
    inc_backup = pfile + ".incumbent"
    cand_file = pfile + ".candidate"

    # 1) fresh data — Kraken needs the trades path (--dl-trades --convert).
    #    Incremental against the persistent datadir, so only the delta is fetched.
    dl = ["freqtrade", "download-data", "--config", cfg, "-p", *PAIRS,
          "--days", str(TRAIN_DAYS + HOLDOUT_DAYS + STARTUP_DAYS), "-t", *tfs,
          "--dl-trades", "--convert", *_dd_args(wd)]
    rc, _ = run(dl, cwd=wd, timeout=7200)
    if rc != 0:
        log(f"download-data failed for {strat}; skipping")
        return None

    # snapshot incumbent params (may not exist -> defaults)
    has_incumbent = os.path.exists(pfile)
    if has_incumbent:
        shutil.copy(pfile, inc_backup)

    # 2) hyperopt on TRAIN -> freqtrade writes best params to <strat>.json
    ho = ["freqtrade", "hyperopt", "--config", cfg, "--config", ovr,
          "--strategy", strat, "--hyperopt-loss", HYPEROPT_LOSS,
          "--spaces", "buy", "sell", "--epochs", str(EPOCHS),
          "--timerange", train, "-p", *PAIRS,
          "-j", JOBS, "--random-state", "42", *_dd_args(wd)]
    rc, _ = run(ho, cwd=wd, timeout=7200)
    if rc != 0 or not os.path.exists(pfile):
        log(f"hyperopt produced no params for {strat}; restoring incumbent")
        if has_incumbent:
            shutil.copy(inc_backup, pfile)
        return None
    shutil.copy(pfile, cand_file)

    # 3) backtest incumbent on HOLDOUT
    if has_incumbent:
        shutil.copy(inc_backup, pfile)
    else:
        os.remove(pfile)  # defaults
    inc_metrics = backtest(wd, cfg, ovr, strat, holdout)

    # 4) backtest candidate on HOLDOUT
    shutil.copy(cand_file, pfile)
    cand_metrics = backtest(wd, cfg, ovr, strat, holdout)

    ok, reason = better(cand_metrics, inc_metrics)
    log(f"{strat}: incumbent={inc_metrics} candidate={cand_metrics}")
    log(f"{strat}: decision={'PROMOTE' if ok else 'KEEP'} — {reason}")

    if not ok:
        # restore incumbent locally
        if has_incumbent:
            shutil.copy(inc_backup, pfile)
        elif os.path.exists(pfile):
            os.remove(pfile)
        _cleanup(inc_backup, cand_file)
        return {"strat": strat, "promoted": False, "reason": reason,
                "incumbent": inc_metrics, "candidate": cand_metrics}

    # candidate is in place (pfile == candidate)
    if can_push and PROMOTE:
        _git_push(wd, strat, pfile, cand_metrics, inc_metrics)
        log(f"{strat}: PROMOTED and pushed -> Railway will redeploy freqtrade-bots")
    else:
        mode = "no GITHUB_TOKEN" if not can_push else "RETRAIN_PROMOTE!=true"
        log(f"{strat}: SHADOW ({mode}) — would promote but NOT pushing to live")
        # restore incumbent so the shadow run leaves nothing changed
        if has_incumbent:
            shutil.copy(inc_backup, pfile)
        elif os.path.exists(pfile):
            os.remove(pfile)
    _cleanup(inc_backup, cand_file)
    return {"strat": strat, "promoted": bool(can_push and PROMOTE), "reason": reason,
            "incumbent": inc_metrics, "candidate": cand_metrics}


def _cleanup(*paths):
    for p in paths:
        try:
            os.remove(p)
        except OSError:
            pass


def _git_push(wd, strat, pfile, cand, inc):
    rel = os.path.relpath(pfile, wd)
    run(["git", "add", rel], cwd=wd)
    msg = (f"auto-retrain: promote {strat} params "
           f"(holdout profit {cand['profit_total']:.4f} vs "
           f"{inc['profit_total'] if inc else 'n/a'})")
    rc, _ = run(["git", "commit", "-m", msg], cwd=wd)
    if rc != 0:
        log(f"{strat}: nothing to commit / commit failed")
        return
    run(["git", "pull", "--rebase", "origin", GIT_BRANCH], cwd=wd)
    rc, _ = run(["git", "push", "origin", GIT_BRANCH], cwd=wd)
    if rc != 0:
        log(f"{strat}: push FAILED (check GITHUB_TOKEN scope = repo)")


def cycle():
    wd, can_push = workdir_setup()
    train, holdout = timeranges()
    log(f"workdir={wd} push={'on' if (can_push and PROMOTE) else 'SHADOW'} "
        f"train={train} holdout={holdout} epochs={EPOCHS} pairs={PAIRS}")
    only = set(filter(None, os.environ.get("RETRAIN_ONLY", "").split(",")))
    results = []
    for strat, (cfg_name, tfs) in STRATEGIES.items():
        if only and strat not in only:
            continue
        try:
            r = retrain_one(wd, can_push, strat, cfg_name, tfs, train, holdout)
            if r:
                results.append(r)
        except Exception as e:  # noqa: BLE001
            log(f"{strat}: ERROR {e}")
    promoted = [r["strat"] for r in results if r.get("promoted")]
    log(f"cycle complete. promoted={promoted or 'none'} "
        f"({len(results)}/{len(STRATEGIES)} strategies evaluated)")


def ensure_datadir():
    """If a persistent DATADIR is configured, make sure it's writable; otherwise
    fall back to the (non-persistent) in-container default so a misconfigured or
    root-owned volume can't crash the loop."""
    global DATADIR
    if not DATADIR:
        return
    try:
        os.makedirs(DATADIR, exist_ok=True)
        probe = os.path.join(DATADIR, ".write_test")
        with open(probe, "w") as f:
            f.write("ok")
        os.remove(probe)
        log(f"using persistent datadir {DATADIR}")
    except Exception as e:  # noqa: BLE001
        log(f"DATADIR {DATADIR} not writable ({e}); falling back to in-container data "
            f"(downloads will not persist across redeploys)")
        DATADIR = ""


def main():
    log("freqtrade auto-retrainer starting")
    ensure_datadir()
    log(f"promote={'ENABLED' if (GITHUB_TOKEN and PROMOTE) else 'SHADOW (safe)'} "
        f"interval={INTERVAL_HOURS}h")
    while True:
        t0 = time.time()
        try:
            cycle()
        except Exception as e:  # noqa: BLE001
            log(f"cycle ERROR {e}")
        if RUN_ONCE:
            log("RETRAIN_ONCE set — exiting after one cycle")
            return
        elapsed = time.time() - t0
        sleep_s = max(60.0, INTERVAL_HOURS * 3600 - elapsed)
        log(f"sleeping {sleep_s/3600:.1f}h until next cycle")
        time.sleep(sleep_s)


if __name__ == "__main__":
    sys.exit(main())
