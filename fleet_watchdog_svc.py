#!/usr/bin/env python3
"""
fleet_watchdog_svc.py — in-service fleet watchdog (the "C layer").

Runs as a guarded daemon thread inside the always-on pnl-dashboard service
(same opt-in pattern as report_emailer). Every WATCHDOG_INTERVAL_SEC (default
300s) it reads the dashboard's own /pnl.json via localhost and evaluates:

  problems  : feed unreachable · feed stale · any bot stale · any bot offline
  warnings  : fleet open positions > WATCHDOG_MAX_OPEN (default 20)
              any bot pnl_daily < WATCHDOG_DAILY_LOSS_ALERT (default -100)

Alerting is TRANSITION-based email via report_emailer.send_email (dormant until
the SMTP_* env vars are set, exactly like the emailer):
  ok -> problems        🚨 alert email
  problem set changes   updated email (min 30-min gap)
  problems -> ok        ✅ recovery email

Current state is always served at /watchdog.json (no auth, no secrets) so the
external GitHub-Actions fleet-watchdog and humans can read it. Read-only
towards the fleet; never raises into the server.

2026-07-08 — added as the in-Railway layer alongside the GH-Actions watchdog.
"""
import json
import os
import threading
import time
import traceback
import urllib.request
import datetime as dt

_LOCK = threading.Lock()
_STATE = {"started": None, "checked_at": None, "problems": [], "warnings": [],
          "snapshot": "", "email_armed": False, "last_email_at": None,
          "last_email_kind": None, "error": None}


def _now_iso():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def get_state():
    with _LOCK:
        return dict(_STATE)


def evaluate(data):
    """Pure function: pnl.json dict -> (problems, warnings, snapshot)."""
    meta = data.get("meta") or {}
    bots = data.get("bots") or []
    problems, warnings = [], []
    if meta.get("feed_stale"):
        problems.append(f"FEED STALE (freshest={meta.get('freshest_update_age_sec')}s)")
    if not bots:
        problems.append("NO BOTS in feed")
    stale = sorted(b.get("bot", "?") for b in bots if b.get("stale"))
    off = sorted(b.get("bot", "?") for b in bots if b.get("status") not in (None, "online"))
    if stale:
        problems.append("STALE: " + ", ".join(stale))
    if off:
        problems.append("NOT ONLINE: " + ", ".join(off))
    # [2026-07-14 APPLES-TO-APPLES FIX] The budget warning summed open_trades
    # over EVERYTHING — shadow twins (modelled copies of their originals),
    # delta-neutral funding books, stocks, the event sniper — and compared
    # that to the 20-position DIRECTIONAL budget, so it read 64-vs-20 on a
    # healthy day and warned forever, drowning real alerts. Warn on the
    # directional cohort only (paper + real-money live trading rows, same
    # cohort fleet_risk budgets); the raw everything-count stays in the
    # snapshot line for context.
    opens, dir_opens = 0, 0
    non_directional = ("perps-funding", "equities-", "event-listing-sniper")
    for b in bots:
        try:
            n = int(b.get("open_trades") or 0)
        except (TypeError, ValueError):
            continue
        opens += n
        if b.get("kind") != "trading":
            continue                      # scanners hold nothing real
        if b.get("venue_mode") in ("lighter_shadow", "lighter_testnet"):
            continue                      # modelled twins double-count originals
        base = b.get("base_bot") or b.get("bot") or ""
        if any(base == p or base.startswith(p) for p in non_directional):
            continue                      # delta-neutral / stocks / event-class
        dir_opens += n
    max_open = int(os.environ.get("WATCHDOG_MAX_OPEN", "20"))
    if dir_opens > max_open:
        warnings.append(f"directional positions {dir_opens} exceed the "
                        f"{max_open}-position budget ({opens} gross incl. shadows)")
    loss_floor = float(os.environ.get("WATCHDOG_DAILY_LOSS_ALERT", "-100"))
    big = [f"{b.get('bot')} ({b.get('pnl_daily'):+.1f})" for b in bots
           if isinstance(b.get("pnl_daily"), (int, float)) and b["pnl_daily"] < loss_floor]
    if big:
        warnings.append("daily P&L below " + str(loss_floor) + ": " + ", ".join(big))
    snapshot = f"bots={len(bots)} open_positions={opens} freshest={meta.get('freshest_update_age_sec')}s"
    return problems, warnings, snapshot


def run_loop(dash):
    """Daemon loop. `dash` is the pnl_dashboard module (for PORT)."""
    try:
        import report_emailer
    except Exception:
        report_emailer = None
    port = int(getattr(dash, "PORT", 8080))
    interval = int(os.environ.get("WATCHDOG_INTERVAL_SEC", "300"))
    min_gap = int(os.environ.get("WATCHDOG_EMAIL_MIN_GAP_SEC", "1800"))
    with _LOCK:
        _STATE["started"] = _now_iso()
    time.sleep(60)  # let the server come up before the first probe
    last_emailed = None      # None = never evaluated-for-email; () = known-good
    last_email_ts = 0.0
    while True:
        try:
            url = f"http://127.0.0.1:{port}/pnl.json?nc={int(time.time())}"
            try:
                with urllib.request.urlopen(url, timeout=20) as r:
                    data = json.load(r)
                problems, warnings, snapshot = evaluate(data)
            except Exception as fe:  # noqa: BLE001
                problems = [f"LOCAL FEED UNREACHABLE: {type(fe).__name__}: {fe}"]
                warnings, snapshot = [], "(no data)"
            armed = bool(report_emailer and report_emailer.smtp_configured())
            cur = tuple(problems)
            now = time.time()
            kind = None
            if cur:
                if last_emailed in (None, ()) or (cur != last_emailed and now - last_email_ts >= min_gap):
                    kind = "alert"
            else:
                if last_emailed not in (None, ()):
                    kind = "recovery"
            if kind and armed:
                subj = ("🚨 fleet-watchdog: " + problems[0][:70]) if kind == "alert" else \
                       "✅ fleet-watchdog: recovered — all bots fresh"
                body_lines = [f"Time: {_now_iso()}", f"Snapshot: {snapshot}", ""]
                if problems:
                    body_lines += ["Problems:"] + ["  - " + p for p in problems]
                if warnings:
                    body_lines += ["Warnings (non-fatal):"] + ["  - " + w for w in warnings]
                body_lines += ["", "State: /watchdog.json on the pnl-dashboard service.",
                               "This is a transition alert (max one per state change, 30-min gap)."]
                if report_emailer.send_email(subj, "\n".join(body_lines)):
                    last_email_ts = now
                    last_emailed = cur if kind == "alert" else ()
                    with _LOCK:
                        _STATE["last_email_at"] = _now_iso()
                        _STATE["last_email_kind"] = kind
            elif kind and not armed:
                # No SMTP configured — remember state anyway so /watchdog.json
                # and logs still show transitions without spamming later.
                last_emailed = cur if kind == "alert" else ()
                print(f"[fleet_watchdog] {kind} (email dormant): {problems or 'ok'}", flush=True)
            elif not cur and last_emailed is None:
                last_emailed = ()
            with _LOCK:
                _STATE.update({"checked_at": _now_iso(), "problems": list(problems),
                               "warnings": list(warnings), "snapshot": snapshot,
                               "email_armed": armed, "error": None})
        except Exception:  # noqa: BLE001
            with _LOCK:
                _STATE["error"] = traceback.format_exc(limit=3)
            print("[fleet_watchdog] loop error:\n" + traceback.format_exc(), flush=True)
        time.sleep(interval)
